# nyx-queue — Usage Patterns

## Producer / Consumer (Python)

```python
import redis

# Producer
p = redis.Redis(port=6381, decode_responses=True)
p.execute_command('ENQUEUE', 'jobs', '{"type": "send_email", "to": "alice@example.com"}')

# Consumer (blocking)
c = redis.Redis(port=6381, decode_responses=True)
while True:
    result = c.execute_command('DEQUEUE', 'jobs')
    if result:
        msg_id, payload = result
        process(payload)
        c.execute_command('ACK', 'jobs', msg_id)
```

## Multiple Consumers (Worker Pool)

```python
import threading, redis

def worker(worker_id):
    c = redis.Redis(port=6381, decode_responses=True)
    while True:
        result = c.execute_command('DEQUEUE', 'jobs')
        msg_id, payload = result
        try:
            process(payload)
            c.execute_command('ACK', 'jobs', msg_id)
        except Exception as e:
            print(f"worker {worker_id}: failed, NACKing: {e}")
            c.execute_command('NACK', 'jobs', msg_id)

for i in range(4):
    threading.Thread(target=worker, args=(i,), daemon=True).start()
```

## Non-Blocking Poll

```python
# Periodic batch processor — poll every second
import time
c = redis.Redis(port=6381, decode_responses=True)
while True:
    result = c.execute_command('DEQUEUE', 'batch_jobs', 'NOWAIT')
    if result:
        msg_id, payload = result
        process(payload)
        c.execute_command('ACK', 'batch_jobs', msg_id)
    else:
        time.sleep(1)
```

## Fan-Out (Multiple Queues)

Producers can send to multiple queues. Each queue is independent:

```python
p = redis.Redis(port=6381, decode_responses=True)
p.execute_command('ENQUEUE', 'email_queue', payload)
p.execute_command('ENQUEUE', 'analytics_queue', payload)
p.execute_command('ENQUEUE', 'audit_queue', payload)
```

## Priority Queues (Convention)

nyx-queue doesn't have built-in priorities, but you can use separate queues with consumer priority:

```python
# Consumer checks high-priority queue first
def consumer():
    while True:
        result = c.execute_command('DEQUEUE', 'high_priority', 'NOWAIT')
        if not result:
            result = c.execute_command('DEQUEUE', 'normal_priority')
        msg_id, payload = result
        # ...
```

## Queue Monitoring

```python
c = redis.Redis(port=6381, decode_responses=True)

# Check depth
depth = c.execute_command('QLEN', 'jobs')
print(f"Queue depth: {depth}")

# Detailed stats
info = c.execute_command('QINFO', 'jobs')
pending, delivered, total_enq, total_ack = info
print(f"Pending: {pending}, In-flight: {delivered}")

# All queues
queues = c.execute_command('QUEUES')
for q in queues:
    depth = c.execute_command('QLEN', q)
    print(f"  {q}: {depth} pending")
```

## Dead Letter Queue (Manual)

nyx-queue doesn't have a built-in DLQ, but you can implement one:

```python
MAX_RETRIES = 3

def consumer_with_dlq():
    c = redis.Redis(port=6381, decode_responses=True)
    retry_counts = {}
    while True:
        result = c.execute_command('DEQUEUE', 'jobs')
        msg_id, payload = result
        retries = retry_counts.get(msg_id, 0)
        try:
            process(payload)
            c.execute_command('ACK', 'jobs', msg_id)
            retry_counts.pop(msg_id, None)
        except Exception:
            if retries >= MAX_RETRIES:
                # Move to DLQ
                c.execute_command('ENQUEUE', 'dead_letter', payload)
                c.execute_command('ACK', 'jobs', msg_id)
                retry_counts.pop(msg_id, None)
            else:
                retry_counts[msg_id] = retries + 1
                c.execute_command('NACK', 'jobs', msg_id)
```
