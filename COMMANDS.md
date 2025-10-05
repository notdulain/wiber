# Wiber Commands - Quick Start Guide

## Setup (One-time)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the System

### 1. Start Multi-Node Cluster with Raft Leader Election (Phase 2 Complete!)
```powershell
python scripts\run_cluster.py
```
**Expected output:**
```
Checking for existing processes on Wiber ports...
No existing processes found on Wiber ports

Loading cluster config: 3 nodes
  - n1: 127.0.0.1:9101
  - n2: 127.0.0.1:9102
  - n3: 127.0.0.1:9103

Starting cluster nodes...
Node n1 started:
  API server: 127.0.0.1:9101 (PING -> PONG)
  RPC server: 127.0.0.1:10101 (inter-node communication)
  Raft state: follower (term 0)
Node n2 started:
  API server: 127.0.0.1:9102 (PING -> PONG)
  RPC server: 127.0.0.1:10102 (inter-node communication)
  Raft state: follower (term 0)
Node n3 started:
  API server: 127.0.0.1:9103 (PING -> PONG)
  RPC server: 127.0.0.1:10103 (inter-node communication)
  Raft state: follower (term 0)

Started 3 nodes

Testing inter-node communication...
[OK] n1 -> n2: PONG
[OK] n1 -> n3: PONG
[OK] n2 -> n1: PONG
[OK] n2 -> n3: PONG
[OK] n3 -> n1: PONG
[OK] n3 -> n2: PONG

Waiting for leader election...

Checking leader election status...
[LEADER] n3 is LEADER (term 1)
[FOLLOWER] n1 is FOLLOWER (term 1)
[FOLLOWER] n2 is FOLLOWER (term 1)

[SUCCESS] n3 is the elected leader!

[SUCCESS] Phase 2 Complete: Raft leader election implemented!
```

### 2. Test Individual Node API (in new terminal)
```powershell
# Activate venv in new terminal
.\venv\Scripts\Activate.ps1

# Test PING on any node
python scripts\test_ping.py
```
**Expected output:**
```
Testing PING against Wiber API server...
Sent: PING
Received: PONG
✅ PING test passed!
```

### 3. Run All Tests
```powershell
python -m pytest -q
```
**Expected output:**
```
........                            [100%]
8 passed in 0.13s
```

### 4. Learn About Raft Algorithm
```powershell
# Open the interactive Raft guide in your browser
start guides\raft-guide.html
```

### 5. Learn About Phase 3: Log Replication
```powershell
# Open the Phase 3 guide to understand what we just built
start guides\phase3-log-replication-guide.html
```

This guide explains in layman's terms:
- What the "memory system" does
- How log replication works
- Before vs after comparison
- Technical implementation details
- Future impact on the system

## Stopping the System
- Press `Ctrl+C` in the terminal running the cluster

## Configuration
- Edit `config/cluster.yaml` to change node settings
- Current setup: 3 nodes (n1, n2, n3) on ports 9101, 9102, 9103
- Each node runs both API server (for clients) and RPC server (for other nodes)

## What Works Now (Phase 3 Complete ✅)
- ✅ Multi-node cluster startup from config
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
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (40 tests passing)
- ✅ **Interactive HTML guides** for learning Raft and Phase 3

## Architecture
```
n1 (9101/10101) ←→ n2 (9102/10102) ←→ n3 (9103/10103)
     ↓                ↓                ↓
  API + RPC        API + RPC        API + RPC
     ↓                ↓                ↓
  FOLLOWER         CANDIDATE        LEADER
```

- **API Server** (9101, 9102, 9103): For client connections
- **RPC Server** (10101, 10102, 10103): For inter-node communication
- **Raft Consensus**: Automatic leader election and state management

