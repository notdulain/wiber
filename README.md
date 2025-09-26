# Wiber - Distributed Messaging System

This repo contains a distributed messaging system prototype implementing core distributed systems concepts for Scenario 3.

## Current Features

The system provides:
- **TCP broker** (server) supporting PUB/SUB and HISTORY commands
- **Publisher client** to send messages with unique IDs and offsets
- **Subscriber client** to receive messages and optionally fetch recent history
- **Persistent per-topic logs** under `data/` (JSONL format with message IDs and offsets)
- **Message deduplication** through unique message IDs
- **Consumer position tracking** through sequential offsets
- **Asynchronous I/O** for handling multiple concurrent clients

## Project structure

- `src/api/broker.py` — asyncio TCP broker
- `src/producer/publisher.py` — simple publisher CLI
- `src/consumer/subscriber.py` — simple subscriber CLI
- `src/database/storage.py` — append/read per-topic logs
- `src/config/settings.py` — host/port and data directory
- `docs/` — place design docs and notes here
- `tests/` — add tests here
- `docker/` — add containerization assets here

## Prerequisites
- Python 3.8+

## Quick start (local)
Open three terminals in the repo root and run:

1) Start the broker:

```bash
python -m src.api.broker
```

2) Start a subscriber (topic: chat), with the last 5 messages on startup:

```bash
python -m src.consumer.subscriber chat --history 5
```

3) Publish a message:

```bash
python -m src.producer.publisher chat "Hello, distributed world!"
```

You should see the subscriber print lines like:
- `HISTORY chat <id> <offset> <ts> <message>` for history entries
- `MSG chat <id> <offset> <ts> Hello, distributed world!` for new messages

Messages are persisted to `./data/chat.log` as JSON lines with unique IDs and offsets. You can restart the broker/subscriber and still fetch history.

## Minimal wire protocol
Client -> Broker:
- `SUB <topic>`
- `PUB <topic> <message...>`
- `HISTORY <topic> <n>`
- `PING` | `QUIT`

Broker -> Client:
- `OK <desc>` | `ERR <desc>`
- `MSG <topic> <id> <offset> <ts> <message>`
- `HISTORY <topic> <id> <offset> <ts> <message>`

## How to extend this into the full assignment (Scenario 3)
Below are the core components you’ll build out, mapped to the scenario’s focus areas:

1) Fault Tolerance
- Redundancy: replicate each topic’s log to multiple broker nodes (e.g., primary + followers).
- Failure detection: heartbeats and timeouts between brokers and from clients to brokers.
- Automatic failover: clients discover a new leader on failure (via a small registry or consensus state).
- Recovery: followers catch up from the leader’s log (or via snapshotting + incremental replication).
- Evaluation: measure latency/throughput with/without replication.

2) Data Replication and Consistency
- Strategy: start with primary–replica and quorum acks (e.g., write succeeds when W out of N replicas ack).
- Consistency model: pick strong (leader-based) or eventual (gossip-based). Justify trade-offs.
- Deduplication: message IDs with idempotent writes and consumer offsets to avoid double delivery.
- Retrieval: index logs by offset/timestamp; allow range reads and pagination for efficient fetch.

3) Time Synchronization
- Synchronize clocks across nodes (NTP) and record both logical and physical timestamps.
- Ordering: use Lamport or vector clocks to reason about causal ordering across brokers.
- Reordering: buffer and reorder on delivery when needed, with bounded waiting.
- Correction: annotate messages with drift/skew metadata for debugging.

4) Consensus and Agreement
- Leader election and log replication with Raft (or Paxos if you prefer).
- Use Raft for: choosing the leader, committing message appends, and agreeing on configuration changes.
- Performance: batch appends, pipeline replication, and tune timeouts.
- Testing: simulate partitions, crashes, and recoveries; verify safety and liveness properties.

5) Integration & Ops
- Service discovery: static config at first, then a simple registry (file/DNS) or a lightweight coordinator.
- Durability: fsync policy, segment the commit log, compaction and snapshots.
- Security: mTLS between components, authN/Z for producers/consumers.
- Observability: structured logs, metrics (latency, throughput, lag), tracing.

## Implemented Features

### Message IDs and Offsets ✅
- **Unique Message IDs**: Each message gets a unique identifier (`msg_{timestamp}_{random_hex}`)
- **Sequential Offsets**: Messages are numbered sequentially within each topic (1, 2, 3, ...)
- **Enhanced Protocol**: Messages now include ID and offset in the wire protocol
- **Deduplication**: Message IDs enable detection and prevention of duplicate processing
- **Position Tracking**: Offsets allow consumers to track their position and resume from specific points

### Message Format
```json
{
  "id": "msg_1758865780040_e10628bb",
  "offset": 3,
  "ts": 1758865780.0369835,
  "msg": "Hello, distributed world!"
}
```

## Next Steps
- **Consumer Groups**: Multiple consumers sharing work and load balancing
- **Message Acknowledgments**: Confirm message receipt and implement retry logic
- **Heartbeats**: Detect dead connections and implement failure detection
- **Multi-broker Architecture**: Split broker into multiple nodes with leader-follower replication
- **Raft Consensus**: Implement leader election and log replication
- **Tests**: Add unit and integration tests under `tests/`

## Distributed Systems Concepts Demonstrated

This system implements several core distributed systems concepts:

### 1. Publisher-Subscriber Pattern
- **Publishers** send messages to specific topics
- **Subscribers** listen to topics they're interested in
- **Broker** acts as intermediary, routing messages from publishers to subscribers

### 2. Message Persistence
- Messages are stored in JSONL files and survive broker restarts
- Enables message durability and replay capabilities
- Foundation for reliable message delivery

### 3. Asynchronous I/O
- Uses Python's `asyncio` for handling multiple clients simultaneously
- Non-blocking operations for better performance and resource utilization
- Enables concurrent message processing

### 4. Message Identification
- **Message IDs**: Unique identifiers for each message
- **Offsets**: Sequential position numbers within topics
- Enables message deduplication and reliable delivery
- Foundation for consumer position tracking

### 5. Topic-based Routing
- Messages are organized by topics (like channels)
- Enables selective message delivery
- Supports multiple message streams

### 6. Client Connection Management
- Tracks active client connections
- Handles client disconnections gracefully
- Manages subscription state

### 7. Simple Wire Protocol
- Text-based commands over TCP
- Easy to understand and debug
- Enables interoperability between different clients

### 8. Error Handling
- Handles connection errors gracefully
- Provides meaningful error messages
- Implements basic fault tolerance

## Notes
- `data/` is git-ignored; safe to delete if you want a fresh state.
- To change host/port or data directory, set env vars: `WIBER_HOST`, `WIBER_PORT`, `WIBER_DATA_DIR`.
