# Wiber - Distributed Messaging System

A distributed messaging system implementing Scenario 3 requirements without Kafka or Docker. Built incrementally with test-driven development.

## Current Status: Phase 0 Complete ✅

**What Works:**
- ✅ Single node startup from YAML configuration
- ✅ PING/PONG API endpoint for health checks
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (10 tests passing)

## Quick Start

```powershell
# Setup (one-time)
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Start a node
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
- `src/cluster/node.py` — Node process that starts API server
- `src/api/wire.py` — TCP server with PING/PONG protocol
- `scripts/run_cluster.py` — Single-node cluster launcher
- `scripts/test_ping.py` — Simple PING test client
- `tests/test_config.py` — Configuration loading tests
- `tests/test_api_ping.py` — API server tests

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

