#!/usr/bin/env python3
"""
E2E: round-trip de persistencia del snapshot .ndb — encolar, apagar, reabrir.

Regresion del 2026-09-10, y la PRIMERA cobertura de mq_save/mq_load: hasta hoy
ninguna suite tocaba el .ndb ni un ciclo real de reinicio, asi que la
persistencia entera —el motivo por el que esta cola se llama «persistent»— no
tenia ni un test.

El bug: el campo «timestamp» del META se escribia con `time_us() / 1000000`,
que es os_monotonic_ns()/1000 escalado — segundos desde el ARRANQUE de la
maquina, no desde epoch. O sea un uptime guardado en disco bajo un nombre que
promete una fecha, en un archivo pensado para sobrevivir reinicios y hasta
cambios de maquina. Nadie lo leia de vuelta (mq_load lo decodificaba y lo
descartaba), asi que era inerte: un dato falso esperando a su primer lector —un
backup, un inspector de .ndb, un «last saved at» en un panel— para volverse un
bug silencioso. Se arreglo a time_epoch() y ademas se le dio un lector, INFO
last_save_epoch, porque un campo que nadie mira se vuelve a pudrir.

Que cubre:
  1. Los mensajes encolados sobreviven a un SIGTERM + reinicio (round-trip del
     .ndb, que no se testeaba).
  2. El contador de msg_id se restaura: el id posterior al reinicio no repite
     ninguno de los de antes.
  3. INFO last_save_epoch es un epoch real (> 2023-11-14), no un uptime.
     Con el bug, ese numero era el uptime de la maquina — en esta, cinco
     ordenes de magnitud mas chico.
  4. El prefijo del msg_id tambien es un epoch real, no un uptime.
  5. Antes del primer save, last_save_epoch es 0 (no un valor inventado).

Uso: python3 test_queue_persist.py [ruta-binario]
"""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BINARY = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "nyx-queue")
TIMEOUT = 5
# 2023-11-14. Cualquier epoch real la supera; un uptime de esta maquina, no.
EPOCH_PISO = 1700000000

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS: %s" % label)
    else:
        failed += 1
        print("  FAIL: %s %s" % (label, detail))


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def send(sock, *args):
    cmd = "*%d\r\n" % len(args)
    for a in args:
        a = str(a)
        cmd += "$%d\r\n%s\r\n" % (len(a), a)
    sock.sendall(cmd.encode())
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\r\n"):
            break
    return data.decode(errors="replace").strip()


def bulk(resp):
    """'$5\\r\\nhola' -> 'hola'; nil -> None."""
    if resp.startswith("$-1"):
        return None
    partes = resp.split("\r\n")
    return partes[1] if len(partes) > 1 else None


def arrancar(workdir, port):
    proc = subprocess.Popen(
        [os.path.abspath(BINARY), "--port", str(port), "--no-rate-limit"],
        cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            s.close()
            return proc
        except OSError:
            time.sleep(0.05)
    proc.kill()
    print("el daemon nunca abrio el puerto %d" % port)
    sys.exit(1)


def info_campo(sock, campo):
    txt = send(sock, "INFO")
    for linea in txt.split("\r\n"):
        if linea.startswith(campo + ":"):
            return linea.split(":", 1)[1]
    return None


def main():
    workdir = tempfile.mkdtemp(prefix="nyxq_persist_")
    port = _free_port()

    # ── Primera vida ────────────────────────────────────────────────────────
    proc = arrancar(workdir, port)
    ids_antes = []
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT)

        # Todavia no se guardo nada: el campo debe decir 0, no inventar una fecha.
        check("last_save_epoch == 0 antes del primer save",
              info_campo(s, "last_save_epoch") == "0",
              repr(info_campo(s, "last_save_epoch")))

        for i in range(3):
            mid = bulk(send(s, "ENQUEUE", "trabajos", "carga-%d" % i))
            check("ENQUEUE trabajos carga-%d devuelve msg_id" % i,
                  mid is not None and "_" in mid, repr(mid))
            ids_antes.append(mid)

        # El prefijo del id es un epoch real, no un uptime. Se compara contra
        # el reloj de pared del propio test, NO contra un piso fijo: el uptime
        # en MICROsegundos (que es lo que devolvia time_us()) supera cualquier
        # piso razonable por accidente pasada la media hora de encendido, asi
        # que un `> EPOCH_PISO` pasaba con el bug puesto. La ventana de 120 s
        # solo la cumple un epoch de verdad.
        prefijo = int(ids_antes[0].split("_")[0])
        ahora = int(time.time())
        check("el prefijo del msg_id es el epoch actual (%d), no un uptime" % prefijo,
              abs(prefijo - ahora) < 120, "prefijo=%d, ahora=%d" % (prefijo, ahora))

        check("QLEN trabajos == 3", send(s, "QLEN", "trabajos") == ":3", repr(send(s, "QLEN", "trabajos")))
        s.close()
    finally:
        # SIGTERM dispara on_shutdown -> mq_save. Es la unica forma de forzar
        # un guardado a demanda: no hay comando SAVE y el bg saver espera 60 s.
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    dump = os.path.join(workdir, "queue.ndb")
    check("el snapshot se escribio al apagar", os.path.exists(dump), dump)
    antes_de_reabrir = int(time.time())

    # ── Segunda vida, mismo directorio ──────────────────────────────────────
    port2 = _free_port()
    proc = arrancar(workdir, port2)
    try:
        s = socket.create_connection(("127.0.0.1", port2), timeout=TIMEOUT)

        check("QLEN trabajos == 3 tras reiniciar (round-trip del .ndb)",
              send(s, "QLEN", "trabajos") == ":3",
              repr(send(s, "QLEN", "trabajos")))

        cargas = []
        for _ in range(3):
            resp = send(s, "DEQUEUE", "trabajos", "NOWAIT")
            cargas.append(resp)
        check("los tres payloads sobrevivieron",
              all("carga-%d" % i in "".join(cargas) for i in range(3)),
              repr(cargas))

        # El contador viene del META y sigue: un id nuevo no repite los viejos.
        nuevo = bulk(send(s, "ENQUEUE", "trabajos", "posterior"))
        check("el msg_id posterior al reinicio no repite ninguno previo",
              nuevo is not None and nuevo not in ids_antes, repr(nuevo))
        contador_nuevo = int(nuevo.split("_")[1])
        contadores_viejos = [int(x.split("_")[1]) for x in ids_antes]
        check("el contador de msg_id se restauro del snapshot (%d > %d)"
              % (contador_nuevo, max(contadores_viejos)),
              contador_nuevo > max(contadores_viejos))

        # EL caso de regresion: el epoch leido del META del .ndb.
        epoca = int(info_campo(s, "last_save_epoch"))
        check("last_save_epoch leido del .ndb es un epoch real (%d), no un uptime"
              % epoca, epoca > EPOCH_PISO, "got %d" % epoca)
        check("last_save_epoch es coherente con el momento del apagado",
              abs(epoca - antes_de_reabrir) < 120,
              "epoca=%d, apagado~%d" % (epoca, antes_de_reabrir))
        s.close()
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("\n%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
