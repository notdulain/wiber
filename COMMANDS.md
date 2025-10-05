# Wiber Commands - Quick Start Guide

## Setup (One-time)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the System

### 1. Start Multi-Node Cluster with Complete Message Storage (Phase 4 Complete!)
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

[SUCCESS] Phase 4 Complete: Message storage with deduplication and topics!
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

### 3. Test Persistent Message Storage
```powershell
# Test that messages are stored permanently on disk
python scripts\test_persistent_storage.py
```
**Expected output:**
```
Testing Persistent Commit Log Integration
==================================================
[OK] Created Raft node: test-node
[OK] Commit log available: True
[OK] Log file: test_data\raft-test-node.log
[OK] Initial entries: 0

Adding 5 test messages...
  [OK] Message 1: SET {'key': 'user:1', 'value': 'Alice'}
  [OK] Message 2: SET {'key': 'user:2', 'value': 'Bob'}
  [OK] Message 3: SET {'key': 'user:3', 'value': 'Charlie'}
  [OK] Message 4: PUB {'topic': 'notifications', 'message': 'Hello World'}
  [OK] Message 5: PUB {'topic': 'notifications', 'message': 'System started'}

Persistent Storage Status:
  Total entries: 5
  Latest offset: 4
  Log file size: 1234 bytes

Reading messages from persistent storage:
  Offset 0: SET {'key': 'user:1', 'value': 'Alice'}
  Offset 1: SET {'key': 'user:2', 'value': 'Bob'}
  Offset 2: SET {'key': 'user:3', 'value': 'Charlie'}

Test completed successfully!
Messages are now stored persistently and will survive restarts!
```

### 4. Run All Tests
```powershell
python -m pytest -q
```
**Expected output:**
```
.s...................................................................... [ 97%]
..                                                                       [100%]
93 passed, 1 skipped, 1 warning in 3.68s
```

### 5. Learn About Raft Algorithm
```powershell
# Open the interactive Raft guide in your browser
start guides\raft-guide.html
```

### 6. Learn About Phase 3: Log Replication
```powershell
# Open the Phase 3 guide to understand log replication
start guides\phase3-log-replication-guide.html
```

### 7. Learn About Phase 4: Message Storage
```powershell
# Open the Phase 4 guide to understand persistent storage
start guides\phase4-message-storage-guide.html
```

This guide explains in layman's terms:
- What the "warehouse" system does
- How persistent storage works
- How duplicate detection works
- How topic organization works
- Real-world applications and impact

## Stopping the System
- Press `Ctrl+C` in the terminal running the cluster

## Configuration
- Edit `config/cluster.yaml` to change node settings
- Current setup: 3 nodes (n1, n2, n3) on ports 9101, 9102, 9103
- Each node runs both API server (for clients) and RPC server (for other nodes)

## What Works Now (Phase 4 Complete ✅)
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
- ✅ **Persistent commit log** - messages survive crashes and restarts
- ✅ **Message deduplication** - automatic duplicate detection and rejection
- ✅ **Topic management** - organize messages by categories (notifications, logs, events)
- ✅ **Per-topic storage** - separate log files for each topic
- ✅ **Topic metadata** - descriptions, retention policies, statistics
- ✅ **Automatic cleanup** - expired topics cleaned up automatically
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (93 tests passing)
- ✅ **Interactive HTML guides** for learning Raft, Phase 3, and Phase 4

## Architecture
```
n1 (9101/10101) ←→ n2 (9102/10102) ←→ n3 (9103/10103)
     ↓                ↓                ↓
  API + RPC        API + RPC        API + RPC
     ↓                ↓                ↓
  FOLLOWER         CANDIDATE        LEADER
     ↓                ↓                ↓
  Persistent       Persistent       Persistent
  Storage          Storage          Storage
  (Topics)         (Topics)         (Topics)
```

- **API Server** (9101, 9102, 9103): For client connections
- **RPC Server** (10101, 10102, 10103): For inter-node communication
- **Raft Consensus**: Automatic leader election and state management
- **Persistent Storage**: Messages stored on disk with deduplication
- **Topic Management**: Messages organized by categories

## What's Coming Next (Phase 5: Client API)
- 🔄 **PUB command** - Publish messages to topics
- 🔄 **SUB command** - Subscribe to topics and receive messages  
- 🔄 **HISTORY command** - Get past messages from topics
- 🔄 **Wire protocol** - Text-based protocol for client communication
- 🔄 **Client libraries** - Easy-to-use client SDKs
- 🔄 **Message routing** - Route messages to correct topics
- 🔄 **Offset tracking** - Track reading progress per client

