# Wiber - Distributed Messaging System (Kafka/Docker-free Skeleton)

This branch provides a clean template to implement Scenario 3 without Kafka or Docker. It sets up the folder structure and empty modules for a custom, multi-node, fault-tolerant messaging system using your own consensus, replication, and time sync.

## Goals (from Scenario 3)
- Fault tolerance: failure detection, replication, failover, recovery.
- Replication & consistency: leader-based or quorum, dedup, fast reads.
- Time sync: physical clock sync, Lamport clocks, bounded reordering.
- Consensus: leader election and log replication (e.g., Raft).
- Integration: coherent, testable system across modules.

## Project Structure

- `src/cluster/` — node process, Raft consensus, and RPC
  - `node.py` — node orchestration (start consensus, API)
  - `raft.py` — Raft state machine and timers
  - `rpc.py` — intra-cluster RPC transport
- `src/api/` — client-facing API
  - `wire.py` — text protocol handlers (SUB/PUB/HISTORY/PING)
- `src/replication/` — commit log and dedup
  - `log.py` — append-only, per-topic commit log API
  - `dedup.py` — producer message ID dedup cache
- `src/time/` — time synchronization and logical clocks
  - `sync.py` — SNTP-style offset estimation
  - `lamport.py` — Lamport clock utility
- `src/config/`
  - `cluster.py` — static cluster config loader
- `config/cluster.yaml` — example cluster topology (3 nodes)
- `scripts/run_cluster.py` — helper to start a local multi-node cluster
- `tests/` — placeholders for Raft, replication, and time sync tests

All modules are stubs; fill them as each team member develops their part.

## Quick Start (skeleton)

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# No external deps required yet
python scripts/run_cluster.py
```

## Contribution Guide (suggested ownership)
- Member 1: Fault tolerance (node lifecycle, failover, recovery)
- Member 2: Replication & consistency (`replication/`, dedup, commit flow)
- Member 3: Time sync (`time/`, reorder strategy)
- Member 4: Consensus (`cluster/raft.py`, elections, AppendEntries)

Coordinate interfaces via:
- Append entries API (leader → followers)
- Commit index propagation
- Client `PUB/SUB/HISTORY` semantics over committed entries

## Notes
- Docker and Kafka assets removed.
- Keep `scenario3.docx` for requirements and evaluation.
- Update this README as modules gain functionality.

