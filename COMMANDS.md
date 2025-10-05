# Wiber Commands - Quick Start Guide

## Setup (One-time)
```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the System

### 1. Start a Single Node
```bash
python scripts\run_cluster.py
```
**Expected output:**
```
Starting node n1 on 127.0.0.1:9101 (PING -> PONG)
Node n1 API server running on 127.0.0.1:9101
Press Ctrl+C to stop
```

### 2. Test the Node (in a new terminal)
```bash
# Activate venv in new terminal
.\venv\Scripts\Activate.ps1

# Test PING
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
```bash
python -m pytest -q
```
**Expected output:**
```
..........                           [100%]
10 passed in 0.10s
```

## Stopping the System
- Press `Ctrl+C` in the terminal running the node

## Configuration
- Edit `config/cluster.yaml` to change node settings
- Current setup: 3 nodes (n1, n2, n3) on ports 9101, 9102, 9103

## What Works Now
- ✅ Single node startup from config
- ✅ PING/PONG API endpoint
- ✅ Configuration validation
- ✅ Test suite

## What's Coming Next
- Multi-node communication
- Raft leader election
- Message replication
- PUB/SUB/HISTORY commands
