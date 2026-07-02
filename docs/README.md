# nyx-queue — Message Queue

nyx-queue is a lightweight, at-least-once message queue using the RESP protocol. Built for reliable task processing with blocking consumers, acknowledgements, and automatic redelivery.

- **Port**: 6381 (default)
- **Protocol**: RESP2 — works with any Redis client or `redis-cli`
- **Delivery**: At-least-once (ACK/NACK based)
- **Blocking consumers**: `DEQUEUE` blocks until a message is available
- **Rate limiting**: 500 req/s per IP (configurable)
- **Persistence**: `.ndb` snapshots via nyx-kv persistence layer

---

## Quick Start

```bash
# Start server
./nyx-queue

# Connect
redis-cli -p 6381

# Produce a message
ENQUEUE jobs '{"type": "email", "to": "alice@example.com"}'
# → "msg_0001"

# Consume (blocking)
DEQUEUE jobs
# → 1) "msg_0001"
#   2) '{"type": "email", "to": "alice@example.com"}'

# Acknowledge
ACK jobs msg_0001
# → +OK
```

---

## Commands

### ENQUEUE `<queue>` `<payload>`

Add a message to the queue. Creates the queue if it doesn't exist.

```
ENQUEUE jobs '{"type": "send_email"}'
→ "msg_0001"
```

Returns a unique message ID.

---

### DEQUEUE `<queue>` `[NOWAIT]`

Consume the next message from the queue.

- Without `NOWAIT`: blocks until a message is available.
- With `NOWAIT`: returns immediately (nil if empty).

```
DEQUEUE jobs
→ 1) "msg_0001"
   2) '{"type": "send_email"}'

DEQUEUE jobs NOWAIT
→ (nil)   # when queue is empty
```

After DEQUEUE, the message enters "delivered" state. It must be ACKed within the ack timeout (default: 30s) or it will be redelivered.

---

### ACK `<queue>` `<msg_id>`

Acknowledge successful processing of a message. Removes it from the queue permanently.

```
ACK jobs msg_0001
→ +OK
```

---

### NACK `<queue>` `<msg_id>`

Negative-acknowledge — requeue the message for redelivery immediately.

```
NACK jobs msg_0001
→ +OK
```

---

### QLEN `<queue>`

Number of pending (not yet delivered) messages in a queue.

```
QLEN jobs
→ 5
```

---

### QINFO `<queue>`

Detailed queue statistics.

```
QINFO jobs
→ 1) "3"   # pending
   2) "2"   # delivered (awaiting ACK)
   3) "100" # total enqueued
   4) "95"  # total acked
```

---

### QUEUES

List all queue names.

```
QUEUES
→ 1) "jobs"
   2) "emails"
   3) "notifications"
```

---

### QDEL `<queue>`

Delete a queue and all its messages.

```
QDEL jobs
→ +OK
```

---

### INFO

Server statistics.

```
INFO
→ # nyx-queue
  version:0.1.0
  ops_total:12345
  connections:8
  total_enqueued:5000
  total_acked:4995
  total_redelivered:12
  ack_timeout:30
```

---

### PING, QUIT

Standard connection commands, same as Redis.

---

## CLI Flags

```bash
./nyx-queue                         # default port 6381
./nyx-queue --rate-limit 1000       # custom rate limit (req/s per IP)
./nyx-queue --no-rate-limit         # disable rate limiting
```

---

## Deployment

```bash
sudo cp deploy/nyx-queue.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nyx-queue
```

→ See [PATTERNS.md](PATTERNS.md) for common usage patterns.
→ See [RELIABILITY.md](RELIABILITY.md) for at-least-once delivery details.
