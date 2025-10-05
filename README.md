# Wiber - Distributed Messaging System

A distributed messaging system implementing Scenario 3 requirements without Kafka or Docker. Built incrementally with test-driven development.

## Current Status: Complete ✅

**What Works:**
- ✅ Multi-node cluster startup from YAML configuration
- ✅ Inter-node communication (RPC ping/pong)
- ✅ **Client API with full wire protocol** (8 commands: PING/PUB/SUB/HISTORY/TOPICS/STATS/HELP/QUIT)
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
- ✅ **User-friendly command interface** - formatted JSON responses
- ✅ **Comprehensive error handling** - clear error messages
- ✅ **Multi-node support** - commands work across all cluster nodes
- ✅ **Real-world scenarios** - email notifications, system monitoring, event streaming
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (93+ tests passing)

## Quick Start

```powershell
# Setup (one-time)
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Start multi-node cluster
python scripts\run_cluster.py

# Connect with interactive client (in new terminal)
.\venv\Scripts\Activate.ps1
python interactive_client.py

# Try these commands:
wiber> PING
wiber> TOPICS
wiber> PUB notifications Hello World!
wiber> STATS notifications
wiber> HELP
```

See [COMMANDS.md](COMMANDS.md) for detailed usage instructions.

## Project Structure

### Core System
- `src/api/wire.py` — Client API server with 8-command wire protocol
- `src/cluster/node.py` — Multi-server node (API + RPC + Raft)
- `src/cluster/raft.py` — Raft consensus algorithm implementation
- `src/cluster/rpc.py` — Inter-node communication (TCP/JSON + RequestVote + AppendEntries)
- `src/replication/log.py` — Persistent commit log with append-only storage
- `src/replication/dedup.py` — Message deduplication using SHA-256 hashing
- `src/replication/topics.py` — Topic management system with metadata
- `src/config/cluster.py` — YAML config loader with validation

### Scripts & Clients
- `scripts/run_cluster.py` — Multi-node cluster launcher with leader election
- `interactive_client.py` — Interactive command-line client with user-friendly output

### Tests
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

### Documentation
- `guides/raft-guide.html` — Interactive Raft algorithm guide
- `guides/phase3-log-replication-guide.html` — Log replication guide
- `guides/phase4-message-storage-guide.html` — Message storage guide
- `guides/plan.txt` — Implementation plan and notes

## Wire Protocol Commands

| Command | Description | Usage |
|---------|-------------|-------|
| **PING** | Test connection | `PING` |
| **PUB** | Publish message | `PUB <topic> <message>` |
| **SUB** | Subscribe to topic | `SUB <topic>` |
| **HISTORY** | Get message history | `HISTORY <topic> [offset] [limit]` |
| **TOPICS** | List available topics | `TOPICS` |
| **STATS** | Show statistics | `STATS [topic]` |
| **HELP** | Show help | `HELP` |
| **QUIT** | Exit client | `QUIT` |

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

## Features

### Distributed Consensus
- **Raft Algorithm**: Leader election and log replication
- **Fault Tolerance**: Automatic failover and recovery
- **Consistency**: Strong consistency across all nodes

### Message Storage
- **Persistent Storage**: Messages survive crashes and restarts
- **Deduplication**: Automatic duplicate message detection
- **Topic Organization**: Messages organized by categories
- **Retention Policies**: Automatic cleanup of expired messages

### Client Interface
- **Interactive Client**: User-friendly command-line interface
- **Wire Protocol**: Text-based protocol for external applications
- **Real-time Subscriptions**: Subscribe to topics for live updates
- **Message History**: Retrieve past messages with pagination

### System Monitoring
- **Statistics**: Topic and cluster-level statistics
- **Health Checks**: Connection testing and status monitoring
- **Error Handling**: Comprehensive error reporting

## Development Approach

Following incremental, test-driven development:
1. **Build** the smallest possible unit
2. **Test** to verify it works
3. **Integrate** into the running system
4. **Repeat** for the next feature

Each phase builds on the previous, ensuring we always have a working system.

## Goals (from Scenario 3)
- **Fault tolerance**: failure detection, replication, failover, recovery
- **Replication & consistency**: leader-based consensus, dedup, fast reads
- **Time sync**: physical clock sync, Lamport clocks, bounded reordering
- **Consensus**: leader election and log replication (Raft)
- **Integration**: coherent, testable system across modules

## License

This project is part of a distributed systems learning exercise implementing Scenario 3 requirements.