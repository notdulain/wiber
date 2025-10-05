# Wiber - Distributed Messaging System

A distributed messaging system implementing Scenario 3 requirements without Kafka or Docker. Built incrementally with test-driven development.

## Current Status: Phase 2 Complete ✅

**What Works:**
- ✅ Multi-node cluster startup from YAML configuration
- ✅ Inter-node communication (RPC ping/pong)
- ✅ Client API (PING/PONG) on all nodes
- ✅ **Raft leader election** with automatic failover
- ✅ **RequestVote RPC** for democratic leader selection
- ✅ **Majority voting** prevents split-brain problems
- ✅ **Term management** handles conflicts gracefully
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (8 tests passing)
- ✅ **Interactive HTML guide** for learning Raft

**What's Coming:**
- Log replication (Phase 3)
- Message storage and deduplication (Phase 4)
- PUB/SUB/HISTORY commands (Phase 5)

## Quick Start

```powershell
# Setup (one-time)
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Start multi-node cluster with Raft leader election
python scripts\run_cluster.py

# Test it (in new terminal)
.\venv\Scripts\Activate.ps1
python scripts\test_ping.py

# Run tests
python -m pytest -q

# Learn about Raft algorithm
start guides\raft-guide.html
```

See [COMMANDS.md](COMMANDS.md) for detailed usage instructions.

## Project Structure

### Implemented Modules
- `src/config/cluster.py` — YAML config loader with validation
- `src/cluster/node.py` — Multi-server node (API + RPC + Raft)
- `src/cluster/raft.py` — Raft consensus algorithm implementation
- `src/cluster/rpc.py` — Inter-node communication (TCP/JSON + RequestVote)
- `src/api/wire.py` — Client API server (PING/PONG protocol)
- `scripts/run_cluster.py` — Multi-node cluster launcher with leader election
- `scripts/test_ping.py` — Simple PING test client
- `tests/test_config.py` — Configuration loading tests
- `tests/test_api_ping.py` — API server tests
- `tests/test_rpc.py` — RPC communication tests
- `tests/test_raft.py` — Raft consensus algorithm tests
- `guides/raft-guide.html` — Interactive HTML guide to Raft algorithm

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
- **Implementation Plan**: `guides/plan.txt` - Detailed phase-by-phase development plan
- **Commands Reference**: `COMMANDS.md` - Complete usage instructions

## Goals (from Scenario 3)
- Fault tolerance: failure detection, replication, failover, recovery
- Replication & consistency: leader-based consensus, dedup, fast reads
- Time sync: physical clock sync, Lamport clocks, bounded reordering
- Consensus: leader election and log replication (Raft)
- Integration: coherent, testable system across modules

