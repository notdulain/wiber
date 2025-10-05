# Wiber Commands - Quick Start Guide

## Setup (One-time)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the System

### 1. Start Multi-Node Cluster (Phase 1 Complete!)
```powershell
python scripts\run_cluster.py
```
**Expected output:**
```
Loading cluster config: 3 nodes
  - n1: 127.0.0.1:9101
  - n2: 127.0.0.1:9102
  - n3: 127.0.0.1:9103

Starting cluster nodes...
Started 3 nodes

============================================================
Testing inter-node communication...
============================================================

Node n1 pinging other nodes:
  ✅ n1 -> n2: PONG
  ✅ n1 -> n3: PONG

Node n2 pinging other nodes:
  ✅ n2 -> n1: PONG
  ✅ n2 -> n3: PONG

Node n3 pinging other nodes:
  ✅ n3 -> n1: PONG
  ✅ n3 -> n2: PONG

✅ Phase 1 Complete: 3 nodes running and communicating!
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
..........                           [100%]
13 passed in 0.10s
```

## Stopping the System
- Press `Ctrl+C` in the terminal running the cluster

## Configuration
- Edit `config/cluster.yaml` to change node settings
- Current setup: 3 nodes (n1, n2, n3) on ports 9101, 9102, 9103
- Each node runs both API server (for clients) and RPC server (for other nodes)

## What Works Now (Phase 1 Complete ✅)
- ✅ Multi-node cluster startup from config
- ✅ Inter-node communication (RPC ping/pong)
- ✅ Client API (PING/PONG) on all nodes
- ✅ Configuration validation and error handling
- ✅ Comprehensive test suite (13 tests passing)

## Architecture
```
n1 (9101/10101) ←→ n2 (9102/10102) ←→ n3 (9103/10103)
     ↓                ↓                ↓
  API + RPC        API + RPC        API + RPC
```

- **API Server** (9101, 9102, 9103): For client connections
- **RPC Server** (10101, 10102, 10103): For inter-node communication
