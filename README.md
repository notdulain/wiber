# Wiber - Distributed Messaging System

A distributed messaging system implementing Scenario 3 requirements without Kafka or Docker. Built incrementally with test-driven development.

## Current Status: Phase 4 Complete ✅

**What Works:**
- ✅ Multi-node cluster startup from YAML configuration
- ✅ Inter-node communication (RPC ping/pong)
- ✅ Client API (PING/PONG) on all nodes
- ✅ **Raft leader election** with automatic failover
- ✅ **RequestVote RPC** for democratic leader selection
- ✅ **Majority voting** prevents split-brain problems
- ✅ **Term management** handles conflicts gracefully
- ✅ **AppendEntries RPC** for log replication
- ✅ **Log consistency checks** for data integrity
- ✅ **Leader replication logic** for message distribution
- ✅ **Follower progress tracking** (next_index, match_index)
- ✅ **Commit index management** for safe message commitment
- ✅ **State machine application** for processing committed messages
- ✅ **Persistent commit log** - messages survive crashes and restarts
- ✅ **Message deduplication** - automatic duplicate detection and rejection
- ✅ **Topic management** - organize messages by categories (notifications, logs, events)
- ✅ **Per-topic storage** - separate log files for each topic
- ✅ **Topic metadata** - descriptions, retention policies, statistics
- ✅ **Automatic cleanup** - expired topics cleaned up automatically
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (93 tests passing)

**What's Coming:**
- PUB/SUB/HISTORY commands (Phase 5)
- Time synchronization (Phase 6)
- Fault tolerance (Phase 7)

## Quick Start

```powershell
# Setup (one-time)
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Start multi-node cluster with complete message storage
python scripts\run_cluster.py

# Test it (in new terminal)
.\venv\Scripts\Activate.ps1
python scripts\test_ping.py

# Test persistent storage
python scripts\test_persistent_storage.py

# Run tests
python -m pytest -q

# Learn about Raft algorithm
start guides\raft-guide.html

# Learn about Phase 3: Log Replication
start guides\phase3-log-replication-guide.html

# Learn about Phase 4: Message Storage
start guides\phase4-message-storage-guide.html
```

See [COMMANDS.md](COMMANDS.md) for detailed usage instructions.

## Project Structure

### Implemented Modules
- `src/config/cluster.py` — YAML config loader with validation
- `src/cluster/node.py` — Multi-server node (API + RPC + Raft)
- `src/cluster/raft.py` — Raft consensus algorithm implementation
- `src/cluster/rpc.py` — Inter-node communication (TCP/JSON + RequestVote + AppendEntries)
- `src/api/wire.py` — Client API server (PING/PONG protocol)
- `src/replication/log.py` — Persistent commit log with append-only storage
- `src/replication/dedup.py` — Message deduplication using SHA-256 hashing
- `src/replication/topics.py` — Topic management system with metadata
- `scripts/run_cluster.py` — Multi-node cluster launcher with leader election
- `scripts/test_ping.py` — Simple PING test client
- `scripts/test_persistent_storage.py` — Persistent storage demonstration
- `tests/test_config.py` — Configuration loading tests
- `tests/test_api_ping.py` — API server tests
- `tests/test_rpc.py` — RPC communication tests
- `tests/test_raft.py` — Raft consensus algorithm tests
- `tests/test_append_entries.py` — AppendEntries RPC tests
- `tests/test_leader_replication.py` — Leader replication logic tests
- `tests/test_commit_index.py` — Commit index management tests
- `tests/test_commit_log.py` — Commit log storage tests
- `tests/test_deduplication.py` — Message deduplication tests
- `tests/test_commit_log_dedup.py` — Integrated deduplication tests
- `tests/test_topic_management.py` — Topic management tests

## Configuration

Edit `config/cluster.yaml` to define your cluster:
```yaml
nodes:
  - id: n1
    host: 127.0.0.1
    port: 9101
  - id: n2
    host: 127.0.0.1
    port: 9102
  - id: n3
    host: 127.0.0.1
    port: 9103
```

## Development Approach

Following incremental, test-driven development:
1. **Build** the smallest possible unit
2. **Test** to verify it works
3. **Integrate** into the running system
4. **Repeat** for the next feature

Each phase builds on the previous, ensuring we always have a working system.

## Learning Resources

- **Interactive Raft Guide**: `guides/raft-guide.html` - Comprehensive HTML guide with visualizations
- **Phase 3 Log Replication Guide**: `guides/phase3-log-replication-guide.html` - Detailed explanation of log replication in layman's terms
- **Phase 4 Message Storage Guide**: `guides/phase4-message-storage-guide.html` - Complete guide to persistent storage, deduplication, and topic management
- **Implementation Plan**: `guides/plan.txt` - Detailed phase-by-phase development plan
- **Commands Reference**: `COMMANDS.md` - Complete usage instructions

## Goals (from Scenario 3)
- Fault tolerance: failure detection, replication, failover, recovery
- Replication & consistency: leader-based consensus, dedup, fast reads
- Time sync: physical clock sync, Lamport clocks, bounded reordering
- Consensus: leader election and log replication (Raft)
- Integration: coherent, testable system across modules

