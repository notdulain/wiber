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

## Quick Start

```bash
# 1) Create/activate a virtualenv (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1

# 2) (Optional) install dependencies if/when they are added
# pip install -r requirements.txt

# 3) Launch the FastAPI gateway + web UI
python scripts/dm_gateway.py

# 4) Open the UI and manage nodes from the browser
# http://127.0.0.1:8080/  (default port unless GATEWAY_PORT is set)
```

From the UI you can:
- Click **Start the cluster** to spawn all nodes defined in `config/cluster.yaml`.
- Use the per-node **Kill** / **Restart** buttons to manage individual nodes.
- Watch each node’s console output live in the three terminals.

Behind the scenes the gateway shells out to `scripts/run_node.py` for each node and
tracks their subprocesses so the UI always knows which nodes are running.

## Command-Line Recipes

### Run a Single Node (detached from the gateway)

```bash
# Replace n1 with the node id from config/cluster.yaml
python scripts/run_node.py --id n1

# Optional flags
#   --config path/to/cluster.yaml   (defaults to config/cluster.yaml)
#   --data-root /custom/data/dir    (defaults to ./.data)
```

Each node writes its console output to `.data/<node_id>/logs/console.log`, which is the
same file the gateway terminals stream in real time.

### Start / Kill / Restart via REST (useful for scripting/tests)

With the gateway running:

```bash
# start all nodes defined in config/cluster.yaml
curl -X POST http://127.0.0.1:8080/cluster/start

# kill a node
curl -X POST http://127.0.0.1:8080/cluster/node/n2/kill

# restart a node (kills if running, then starts it)
curl -X POST http://127.0.0.1:8080/cluster/node/n3/restart

# inspect running state for each node
curl http://127.0.0.1:8080/cluster/nodes
```

### Legacy Helper (manual multi-node run)

`scripts/run_cluster.py` still exists as a simple reference launcher that starts the nodes
inside the same Python process. The new gateway/UI flow is preferred, but you can still run:

```bash
python scripts/run_cluster.py
```

This script lacks lifecycle controls, so you must terminate it with `Ctrl+C`.

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
