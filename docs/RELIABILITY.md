# nyx-queue — Reliability & Delivery Guarantees

## Delivery Semantics

nyx-queue provides **at-least-once** delivery:

- Every message is delivered to **at least one** consumer.
- A message may be delivered **more than once** if the consumer crashes before ACKing.
- Messages are **never lost** while the server is running (pending and delivered messages are in memory).
- Persistence to `.ndb` snapshot preserves messages across planned restarts.

## Message States

```
ENQUEUE → [pending] → DEQUEUE → [delivered] → ACK → [gone]
                                            → NACK → [pending] (requeued)
                                   (timeout) → [pending] (redelivered)
```

| State | Description |
|-------|-------------|
| `pending` | Waiting in queue, not yet delivered |
| `delivered` | Sent to a consumer, awaiting ACK/NACK |
| `gone` | Successfully ACKed and removed |

## ACK Timeout & Redelivery

After `DEQUEUE`, a message enters "delivered" state. If no `ACK` or `NACK` arrives within **30 seconds** (configurable via `ack_timeout`), the message is automatically redelivered to the next available consumer.

This means:

- If your consumer crashes mid-processing, the message will be redelivered after 30s.
- **Your consumers must be idempotent** — they may process the same message more than once.

## Making Consumers Idempotent

Use the message ID as an idempotency key:

```python
def process_message(msg_id, payload):
    if redis_client.set(f"processed:{msg_id}", "1", nx=True, ex=3600):
        # First time seeing this message — process it
        do_work(payload)
    # else: already processed, skip
    c.execute_command('ACK', 'jobs', msg_id)
```

Or use a database unique constraint:

```sql
INSERT INTO jobs_processed (msg_id, result) VALUES (?, ?)
ON CONFLICT (msg_id) DO NOTHING
```

## Ordering

Messages within a single queue are delivered in **FIFO order** (first in, first out). NACK requeues at the front of the queue, so a repeatedly-failing message can block others — use a Dead Letter Queue pattern (see PATTERNS.md) to avoid this.

With multiple consumers, FIFO order is not guaranteed globally — each consumer gets the next available message, but processing order depends on consumer speed.

## Persistence

nyx-queue writes `.ndb` snapshots to disk. The backup timer (see `deploy/nyx-backup.service`) copies `queue.ndb` daily with 7-day retention.

Messages in `delivered` state at the time of a crash are redelivered on restart (they were not yet ACKed, so they are treated as pending).

## What nyx-queue Does Not Provide

- **Exactly-once delivery**: not possible without distributed consensus (see idempotency above).
- **Message ordering across queues**: each queue is independent.
- **Message TTL / expiry**: messages don't expire (use QDEL to purge a queue).
- **Message filtering / routing**: use separate queues or implement in the consumer.
- **Durable subscriptions**: consumer state is not persisted — a crashed consumer loses its position (unlike Kafka). Use ACK/NACK to handle this.
