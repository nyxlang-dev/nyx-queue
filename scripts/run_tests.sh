#!/bin/bash
# run_tests.sh — levanta el daemon de referencia en puerto de test y corre
# la suite Python (17 tests RESP2). Adaptado de test_queue() del runner del
# monorepo al extraerse el producto (2026-07-05).
set -uo pipefail
STACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STACK"
PORT="${QUEUE_TEST_PORT:-16381}"
BIN="${NYX_QUEUE_BIN:-$STACK/nyx-queue}"

[ -x "$BIN" ] || { echo "error: $BIN not built (make build)"; exit 1; }

SERVER_PID=""
cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true; sleep 0.3
        kill -9 "$SERVER_PID" 2>/dev/null || true
    fi
    rm -f queue.ndb
}
trap cleanup EXIT

echo "Starting nyx-queue on port $PORT..."
"$BIN" --port "$PORT" --no-rate-limit >/dev/null 2>&1 &
SERVER_PID=$!

retries=0
while ! (echo > /dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; do
    retries=$((retries + 1))
    [ $retries -ge 30 ] && { echo "error: not listening on $PORT"; exit 1; }
    sleep 0.1
done

python3 tests/test_nyx_queue.py 127.0.0.1 "$PORT"
