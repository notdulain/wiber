# Wiber - Distributed Messaging System (Demo)

This repo contains a minimal working demo of a distributed messaging system prototype to get you started for Scenario 3.

The demo uses only Python's standard library (no extra installs) and provides:
- A TCP broker (server) supporting PUB/SUB and HISTORY commands
- A publisher client to send messages
- A subscriber client to receive messages and optionally fetch recent history
- Persistent per-topic logs under `data/` (JSONL format)

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
python3 -m src.api.broker
```

2) Start a subscriber (topic: chat), with the last 5 messages on startup:

```bash
python3 -m src.consumer.subscriber chat --history 5
```

3) Publish a message:

```bash
python3 -m src.producer.publisher chat "Hello, distributed world!"
```

You should see the subscriber print lines like:
- `HISTORY chat <ts> <message>` for history entries
- `MSG chat <ts> Hello, distributed world!` for new messages

Messages are persisted to `./data/chat.log` as JSON lines. You can restart the broker/subscriber and still fetch history.

## Minimal wire protocol
Client -> Broker:
- `SUB <topic>`
- `PUB <topic> <message...>`
- `HISTORY <topic> <n>`
- `PING` | `QUIT`

Broker -> Client:
- `OK <desc>` | `ERR <desc>`
- `MSG <topic> <ts> <message>`
- `HISTORY <topic> <ts> <message>`

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

## Next steps
- Split the broker into multiple nodes and implement a basic leader–follower replication.
- Add message IDs and per-consumer offsets.
- Introduce simple Raft for leader election and commit agreement.
- Add tests under `tests/` (unit + integration) and basic benchmarks.

## Notes
- `data/` is git-ignored; safe to delete if you want a fresh state.
- To change host/port or data directory, set env vars: `WIBER_HOST`, `WIBER_PORT`, `WIBER_DATA_DIR`.
