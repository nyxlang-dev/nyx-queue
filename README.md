# nyx-queue

Persistent message queue library for [Nyx](https://nyxlang.com).
RESP2 wire protocol, ACK-based delivery with automatic redelivery,
multiple consumers with round-robin dispatch, per-IP rate limiting,
and binary `.ndb` persistence. Consume it as a package or run the
reference standalone daemon directly.

Librería de cola de mensajes persistente escrita en Nyx.
Protocolo RESP2, entrega basada en ACK con reenvío automático,
múltiples consumidores round-robin, rate limiting por IP y persistencia `.ndb`.
Se consume como paquete PM o se ejecuta como daemon standalone de referencia.

---

## Install

Install the Nyx toolchain:

```bash
curl -sSf https://nyxlang.com/install.sh | sh
```

## Quick start

```bash
git clone https://github.com/nyxlang-dev/nyx-queue
cd nyx-queue
nyx build
./nyx-queue [flags]
```

## Usage

Build and run the standalone daemon:

```bash
make build          # compiles examples/standalone.nx
./nyx-queue         # listens on :6381
```

Connect with any Redis client:

```bash
redis-cli -p 6381
> ENQUEUE jobs "process item 42"
OK
> DEQUEUE jobs
1) "msg-abc123"
2) "process item 42"
> ACK jobs msg-abc123
OK
> QLEN jobs
(integer) 0
> QLIST
1) "jobs"
```

### Embed as a library

```toml
# nyx.toml
[dependencies]
nyx-queue = "*"
```

```nyx
import "std/resp"
import "nyx-queue/src/store"
import "nyx-queue/src/commands"
// ... your own CLI handling + accept loop
```

See `examples/standalone.nx` for full reference wiring (CLI flags, 64 workers, background saver, redelivery checker).

## Commands

| Command | Description |
|---------|-------------|
| `ENQUEUE queue message` | Add a message to the queue |
| `DEQUEUE queue` | Get the next message — returns `[msg_id, message]` |
| `ACK queue msg_id` | Acknowledge a message (removes it from pending) |
| `QLEN queue` | Get queue length |
| `QDEL queue` | Delete an entire queue |
| `QLIST` | List all queues |
| `PING` | Health check |
| `INFO` | Server info |

## Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--port N` | `6381` | TCP port to listen on |
| `--ack-timeout N` | `30` | Seconds before unacknowledged messages are redelivered |
| `--rate-limit N` | `500` | Max requests per second per IP |
| `--no-rate-limit` | — | Disable rate limiting entirely |

```bash
./nyx-queue --port 6391 --ack-timeout 60 --rate-limit 1000
./nyx-queue --no-rate-limit   # for development / testing
```

## Documentation

See [docs/](./docs/) for full reference:

- [docs/COMMANDS.md](./docs/COMMANDS.md) — full command reference with examples
- [docs/PATTERNS.md](./docs/PATTERNS.md) — producer/consumer patterns
- [docs/RELIABILITY.md](./docs/RELIABILITY.md) — ACK semantics, redelivery, persistence guarantees

## Limitations

- No job scheduling — delivery order is strictly FIFO
- No priority queues
- No automatic dead-letter queue — unacknowledged messages stay in pending indefinitely until redelivered
- No authentication — any client can connect
- No Pub/Sub (see nyx-kv for that)

## License

Apache 2.0 — see [LICENSE](../../LICENSE)
