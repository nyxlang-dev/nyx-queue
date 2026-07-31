#!/usr/bin/env python3
"""
Test suite para nyx-queue — verifica los comandos principales
Uso: python3 test_nyx_queue.py [host] [port]
Default: localhost 6381

Puede ejecutarse contra un servidor ya corriendo o el runner lo levanta automaticamente.
"""

import socket
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 6381
TIMEOUT = 5

passed = 0
failed = 0

def send_command(sock, *args):
    """Envia un comando RESP y lee la respuesta"""
    cmd = f"*{len(args)}\r\n"
    for arg in args:
        arg = str(arg)
        cmd += f"${len(arg)}\r\n{arg}\r\n"
    sock.sendall(cmd.encode())
    return read_response(sock)

def read_response(sock):
    """Lee una respuesta RESP"""
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\r\n"):
            break
    return data.decode().strip()

def connect():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    sock.connect((HOST, PORT))
    return sock

def test(name, actual, expected):
    global passed, failed
    ok = expected in actual
    if ok:
        print(f"  PASS {name}")
        passed += 1
    else:
        print(f"  FAIL {name}")
        print(f"     Expected: {expected}")
        print(f"     Got:      {actual}")
        failed += 1

# ==============================
print(f"\nConnecting to nyx-queue at {HOST}:{PORT}...")
try:
    sock = connect()
    print("   Connected!\n")
except Exception as e:
    print(f"   FAIL Could not connect: {e}")
    sys.exit(1)

# ==============================
print("=== TEST 1: PING ===")
resp = send_command(sock, "PING")
test("PING returns PONG", resp, "PONG")

# ==============================
print("\n=== TEST 2: ENQUEUE ===")
resp = send_command(sock, "ENQUEUE", "test:jobs", "payload_one")
test("ENQUEUE returns message ID", resp, "_")  # ID format: timestamp_counter
msg_id_1 = resp.split("\r\n")[-1] if "\r\n" in resp else resp.lstrip("$0123456789\r\n")

resp = send_command(sock, "ENQUEUE", "test:jobs", "payload_two")
test("ENQUEUE second message", resp, "_")

resp = send_command(sock, "ENQUEUE", "test:jobs", "payload_three")
test("ENQUEUE third message", resp, "_")

# ==============================
print("\n=== TEST 3: QLEN ===")
resp = send_command(sock, "QLEN", "test:jobs")
test("QLEN = 3", resp, "3")

# ==============================
print("\n=== TEST 4: DEQUEUE NOWAIT ===")
resp = send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
test("DEQUEUE returns payload_one", resp, "payload_one")
# Extract message ID from the array response for ACK later
lines = resp.split("\r\n")
dequeued_id = None
for i, line in enumerate(lines):
    if line.startswith("$") and i + 1 < len(lines) and "_" in lines[i + 1]:
        dequeued_id = lines[i + 1]
        break

# ==============================
print("\n=== TEST 5: ACK ===")
if dequeued_id:
    resp = send_command(sock, "ACK", "test:jobs", dequeued_id)
    test("ACK returns OK", resp, "OK")
else:
    print("  SKIP ACK (no message ID captured)")

# ==============================
print("\n=== TEST 6: DEQUEUE + NACK ===")
resp = send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
test("DEQUEUE second message", resp, "payload_two")
# Extract ID
lines = resp.split("\r\n")
nack_id = None
for i, line in enumerate(lines):
    if line.startswith("$") and i + 1 < len(lines) and "_" in lines[i + 1]:
        nack_id = lines[i + 1]
        break
if nack_id:
    resp = send_command(sock, "NACK", "test:jobs", nack_id)
    test("NACK returns OK", resp, "OK")
else:
    print("  SKIP NACK (no message ID captured)")

# ==============================
print("\n=== TEST 7: QINFO ===")
resp = send_command(sock, "QINFO", "test:jobs")
test("QINFO returns stats", resp, "*4")

# ==============================
print("\n=== TEST 8: QUEUES ===")
resp = send_command(sock, "QUEUES")
test("QUEUES lists test:jobs", resp, "test:jobs")

# ==============================
print("\n=== TEST 9: INFO ===")
resp = send_command(sock, "INFO")
test("INFO returns server info", resp, "nyx-queue")

# ==============================
print("\n=== TEST 10: DEQUEUE empty (NOWAIT) ===")
# Drain remaining messages first
send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
resp = send_command(sock, "DEQUEUE", "test:jobs", "NOWAIT")
test("DEQUEUE empty returns nil", resp, "$-1")

# ==============================
print("\n=== TEST 11: QDEL ===")
resp = send_command(sock, "QDEL", "test:jobs")
test("QDEL returns OK", resp, "OK")

resp = send_command(sock, "QLEN", "test:jobs")
test("QLEN after QDEL = 0", resp, ":0")

# ==============================
print("\n=== TEST 12: Error handling ===")
resp = send_command(sock, "ENQUEUE", "test:err")
test("ENQUEUE without payload errors", resp, "ERR")

resp = send_command(sock, "QDEL", "nonexistent")
test("QDEL nonexistent errors", resp, "ERR")

# ==============================
print("\n=== TEST 13: Cleanup ===")
send_command(sock, "QDEL", "test:jobs")
print("  Cleanup done")

sock.close()

print(f"\n{'=' * 40}")
print(f"  Results: {passed} passed  {failed} failed")
print(f"  Total: {passed + failed} tests")
print(f"{'=' * 40}\n")

sys.exit(1 if failed > 0 else 0)
