# Wiber Commands - Quick Start Guide

## Setup (One-time)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the System

### 1. Start Multi-Node Cluster
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
  API server: 127.0.0.1:9101 (PING/PUB/SUB/HISTORY/TOPICS/STATS/HELP)
  RPC server: 127.0.0.1:10101 (inter-node communication)
  Raft state: follower (term 0)
  Topics: notifications, logs, events

Waiting for leader election...
[LEADER] n1 is LEADER (term 1)
[FOLLOWER] n2 is FOLLOWER (term 1)
[FOLLOWER] n3 is FOLLOWER (term 1)
[SUCCESS] n1 is the elected leader!
Press Ctrl+C to stop all nodes...
```

### 2. Connect with Interactive Client
```powershell
# Activate venv in new terminal
.\venv\Scripts\Activate.ps1

# Start interactive client
python interactive_client.py
```

## Available Commands

### Core Commands
| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| **PING** | Test connection to server | `PING` | `PING` |
| **PUB** | Publish a message to a topic | `PUB <topic> <message>` | `PUB notifications Hello World!` |
| **SUB** | Subscribe to a topic for real-time messages | `SUB <topic>` | `SUB notifications` |
| **HISTORY** | Get message history from a topic | `HISTORY <topic> [offset] [limit]` | `HISTORY notifications 0 10` |

### Information Commands
| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| **TOPICS** | List all available topics with details | `TOPICS` | `TOPICS` |
| **STATS** | Show statistics for a topic or cluster | `STATS [topic]` | `STATS notifications` |
| **HELP** | Show all available commands with usage | `HELP` | `HELP` |
| **QUIT** | Exit the client | `QUIT` | `QUIT` |

## Interactive Client Examples

### Basic Usage
```bash
wiber> PING
Response: PONG

wiber> PUB notifications Hello World!
Response: OK 34

wiber> SUB notifications
Response: OK subscribed to notifications

wiber> HISTORY notifications 30 5
Response: OK {"topic": "notifications", "offset": 30, "limit": 5, "count": 4, "messages": [...]}

📚 4 messages in 'notifications':
  [30] Hello from Python client!
  [31] This is a test message
  [32] Hello World!
  [33] Hello Brothers!!!
```

### Information Commands
```bash
wiber> TOPICS
Response: OK {"topics": [...], "count": 3}

📋 Available Topics (3):
  • notifications
    Description: User notifications
    Retention: 24 hours

  • logs
    Description: System logs
    Retention: 48 hours

  • events
    Description: Application events
    Retention: 72 hours

wiber> STATS notifications
Response: OK {"topic": "notifications", "message_count": 34, ...}

📊 Statistics for 'notifications':
  Messages: 34
  Latest Offset: 33
  Subscribers: 1
  Deduplication: Enabled
  Retention: 24 hours

wiber> HELP
Response: OK {"commands": [...]}

❓ Available Commands:
  PING       - Test connection to server
    Usage: PING

  PUB        - Publish a message to a topic
    Usage: PUB <topic> <message>

  TOPICS     - List all available topics
    Usage: TOPICS
```

## Real-World Use Cases

### 1. System Monitoring
```bash
# Subscribe to system logs
SUB logs

# Check log statistics
STATS logs

# Get recent log entries
HISTORY logs 0 20
```

### 2. User Notifications
```bash
# Publish user notification
PUB notifications User alice logged in successfully

# Subscribe to notifications
SUB notifications

# Check notification count
STATS notifications
```

### 3. Application Events
```bash
# Publish application event
PUB events Payment processed: order_123

# Get event history
HISTORY events 0 50

# Check all topics
TOPICS
```

## Stopping the System
- Press `Ctrl+C` in the terminal running the cluster

## Configuration
- Edit `config/cluster.yaml` to change node settings
- Current setup: 3 nodes (n1, n2, n3) on ports 9101, 9102, 9103
- Each node runs both API server (for clients) and RPC server (for other nodes)

## What Works Now (Complete ✅)
- ✅ Multi-node cluster startup from config
- ✅ Inter-node communication (RPC ping/pong)
- ✅ **Client API with full wire protocol** (8 commands total)
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
- ✅ **User-friendly command output** - formatted JSON responses
- ✅ **Comprehensive error handling** - clear error messages
- ✅ **Multi-node support** - commands work across all cluster nodes
- ✅ **Real-world scenarios** - email notifications, system monitoring, event streaming
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (93+ tests passing)
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

- **API Server** (9101, 9102, 9103): For client connections with full wire protocol
- **RPC Server** (10101, 10102, 10103): For inter-node communication
- **Raft Consensus**: Automatic leader election and state management
- **Persistent Storage**: Messages stored on disk with deduplication
- **Topic Management**: Messages organized by categories
- **Wire Protocol**: 8 commands for external applications (PING, PUB, SUB, HISTORY, TOPICS, STATS, HELP, QUIT)