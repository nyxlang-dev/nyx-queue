# nyx-queue — Command Reference

Connect with `redis-cli -p 6381` or any Redis client library pointing to port 6381.

---

## ENQUEUE

```
ENQUEUE <queue> <payload>
→ "<msg_id>"
```

Adds `payload` to `queue`. The queue is created automatically on first use. Message IDs are sequential strings (`msg_0001`, `msg_0002`, ...) scoped per queue.

**Returns**: Bulk string message ID.

---

## DEQUEUE

```
DEQUEUE <queue>
→ 1) "<msg_id>"
   2) "<payload>"

DEQUEUE <queue> NOWAIT
→ (nil)  or  1) "<msg_id>" 2) "<payload>"
```

Removes and returns the next message from the front of the queue.

- **Blocking** (default): connection blocks until a message is available. Multiple consumers can block on the same queue; messages are delivered round-robin.
- **Non-blocking** (NOWAIT): returns immediately with nil if the queue is empty.

After DEQUEUE, the message is in "delivered" state and must be ACKed within `ack_timeout` seconds (default 30s) or it will be redelivered.

**Returns**: 2-element RESP array `[msg_id, payload]`, or nil (NOWAIT only).

---

## ACK

```
ACK <queue> <msg_id>
→ +OK
→ -ERR message not found or not delivered
```

Acknowledge that the message was processed successfully. Permanently removes it.

**Returns**: `+OK` or error.

---

## NACK

```
NACK <queue> <msg_id>
→ +OK
→ -ERR message not found
```

Reject the message. It is immediately requeued at the front of the queue for redelivery.

**Returns**: `+OK` or error.

---

## QLEN

```
QLEN <queue>
→ <integer>
```

Number of messages currently pending (waiting to be DEQUEUEd). Does not count messages in delivered state.

**Returns**: Integer.

---

## QINFO

```
QINFO <queue>
→ 1) "<pending>"
   2) "<delivered>"
   3) "<total_enqueued>"
   4) "<total_acked>"
```

| Field | Description |
|-------|-------------|
| `pending` | Messages waiting to be delivered |
| `delivered` | Messages delivered but not yet ACKed |
| `total_enqueued` | Lifetime total messages enqueued |
| `total_acked` | Lifetime total messages acknowledged |

**Returns**: 4-element RESP array of integer strings.

---

## QUEUES

```
QUEUES
→ 1) "jobs"
   2) "emails"
```

List all known queues (including empty ones that haven't been deleted).

**Returns**: RESP array of bulk strings.

---

## QDEL

```
QDEL <queue>
→ +OK
→ -ERR queue not found
```

Delete a queue and all its messages (pending and delivered). Consumers blocking on this queue will receive nil on next wakeup.

**Returns**: `+OK` or error.

---

## INFO

```
INFO
→ "# nyx-queue\r\nversion:0.1.0\r\n..."
```

Returns server statistics as a multi-line bulk string:

| Field | Description |
|-------|-------------|
| `version` | nyx-queue version |
| `ops_total` | Total commands processed |
| `connections` | Current active connections |
| `total_enqueued` | Lifetime messages enqueued |
| `total_acked` | Lifetime messages acked |
| `total_redelivered` | Messages redelivered after ACK timeout |
| `ack_timeout` | Current ACK timeout in seconds |

---

## PING

```
PING
→ PONG

PING "hello"
→ "hello"
```

---

## QUIT

```
QUIT
→ +OK
```

Closes the connection gracefully.
