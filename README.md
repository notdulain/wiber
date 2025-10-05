# Wiber - Distributed Messaging System

A distributed messaging system implementing Scenario 3 requirements without Kafka or Docker. Built incrementally with test-driven development.

## Current Status: Phase 1 Complete ✅

**What Works:**
- ✅ Multi-node cluster startup from YAML configuration
- ✅ Inter-node communication (RPC ping/pong)
- ✅ Client API (PING/PONG) on all nodes
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (13 tests passing)

**What's Coming:**
- Raft leader election (Phase 2)
- Message replication (Phase 3)
- PUB/SUB/HISTORY commands (Phase 5)

## Quick Start

```powershell
# Setup (one-time)
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Start multi-node cluster
python scripts\run_cluster.py

# Test it (in new terminal)
.\venv\Scripts\Activate.ps1
python scripts\test_ping.py

# Run tests
python -m pytest -q
```

See [COMMANDS.md](COMMANDS.md) for detailed usage instructions.

## Project Structure

### Implemented Modules
- `src/config/cluster.py` — YAML config loader with validation
- `src/cluster/node.py` — Multi-server node (API + RPC)
- `src/cluster/rpc.py` — Inter-node communication (TCP/JSON)
- `src/api/wire.py` — Client API server (PING/PONG protocol)
- `scripts/run_cluster.py` — Multi-node cluster launcher with communication tests
- `scripts/test_ping.py` — Simple PING test client
- `tests/test_config.py` — Configuration loading tests
- `tests/test_api_ping.py` — API server tests
- `tests/test_rpc.py` — RPC communication tests

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

## Goals (from Scenario 3)
- Fault tolerance: failure detection, replication, failover, recovery
- Replication & consistency: leader-based consensus, dedup, fast reads
- Time sync: physical clock sync, Lamport clocks, bounded reordering
- Consensus: leader election and log replication (Raft)
- Integration: coherent, testable system across modules

