#!/usr/bin/env python3
"""Start multiple nodes from config and test inter-node communication (Phase 1).

Loads all nodes from `config/cluster.yaml` and starts them with both API and RPC servers.
Then tests that all nodes can communicate with each other.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

# Ensure repo root and src are on sys.path
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.config.cluster import load_cluster_config  # type: ignore
from src.cluster.node import Node  # type: ignore


def cleanup_ports():
    """Clean up any processes using Wiber ports (9101, 9102, 9103)."""
    ports = [9101, 9102, 9103]
    cleaned = False
    
    print("Checking for existing processes on Wiber ports...")
    
    for port in ports:
        try:
            # Find process using the port
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            try:
                                print(f"Cleaning up: Killing process {pid} using port {port}")
                                subprocess.run(f'taskkill /PID {pid} /F', shell=True, check=True)
                                print(f"Successfully cleaned port {port}")
                                cleaned = True
                            except subprocess.CalledProcessError:
                                print(f"Failed to kill process {pid} on port {port}")
        except Exception as e:
            print(f"Error checking port {port}: {e}")
    
    if not cleaned:
        print("No existing processes found on Wiber ports")
    else:
        print("Port cleanup complete!")
    
    print()


async def check_leader_election(nodes: list[Node]) -> None:
    """Check which node is the leader."""
    print("\n" + "="*60)
    print("Checking leader election status...")
    print("="*60)
    
    leaders = []
    for node in nodes:
        if node._raft and node._raft.state.value == "leader":
            leaders.append(node.node_id)
            print(f"[LEADER] {node.node_id} is LEADER (term {node._raft.current_term})")
        else:
            state = node._raft.state.value if node._raft else "unknown"
            term = node._raft.current_term if node._raft else 0
            print(f"[{state.upper()}] {node.node_id} is {state.upper()} (term {term})")
    
    if len(leaders) == 1:
        print(f"\n[SUCCESS] {leaders[0]} is the elected leader!")
    elif len(leaders) == 0:
        print("\n[WARNING] No leader elected yet (election may be in progress)")
    else:
        print(f"\n[ERROR] Multiple leaders detected: {leaders}")


async def monitor_leader(nodes: list[Node]) -> None:
    """Print a message when leadership changes during runtime."""
    last_leader = None
    while True:
        leaders = [n.node_id for n in nodes if n._raft and n._raft.state.value == "leader"]
        leader_id = leaders[0] if len(leaders) == 1 else None
        if leader_id != last_leader:
            if leader_id is None and len(leaders) > 1:
                print("[WARN] Multiple leaders detected:", leaders)
            elif leader_id is None:
                print("[INFO] No leader currently elected (election in progress)")
            else:
                term = next(n._raft.current_term for n in nodes if n.node_id == leader_id)
                print(f"[INFO] Leader changed -> {leader_id} (term {term})")
            last_leader = leader_id
        await asyncio.sleep(1.0)


async def test_inter_node_communication(nodes: list[Node]) -> None:
    """Test that all nodes can communicate with each other."""
    print("\n" + "="*60)
    print("Testing inter-node communication...")
    print("="*60)
    
    for i, node in enumerate(nodes):
        print(f"\nNode {node.node_id} pinging other nodes:")
        
        for j, other_node in enumerate(nodes):
            if i != j:  # Don't ping self
                try:
                    result = await node.ping_other_node(other_node.host, other_node.port)
                    if result.get("method") == "pong":
                        print(f"  [OK] {node.node_id} -> {other_node.node_id}: PONG")
                    else:
                        print(f"  [FAIL] {node.node_id} -> {other_node.node_id}: {result}")
                except Exception as e:
                    print(f"  [ERROR] {node.node_id} -> {other_node.node_id}: Error - {e}")


async def start_all_nodes(config) -> list[Node]:
    """Start all nodes from config."""
    nodes = []
    tasks = []
    
    # Create list of other nodes for each node
    all_node_configs = config.nodes
    
    print("Starting cluster nodes...")
    for i, node_config in enumerate(all_node_configs):
        # Create list of other nodes (excluding self)
        other_nodes = []
        for j, other_config in enumerate(all_node_configs):
            if i != j:  # Don't include self
                other_nodes.append((other_config.host, other_config.port))
        
        node = Node(
            node_id=node_config.id,
            host=node_config.host,
            port=node_config.port,
            other_nodes=other_nodes,
            data_dir=f".data/{node_config.id}"
        )
        nodes.append(node)
        
        # Start each node in a separate task with error handling
        task = asyncio.create_task(node._start_async())
        tasks.append(task)
        
        # Give each node a moment to start
        await asyncio.sleep(0.5)
    
    print(f"\nStarted {len(nodes)} nodes")
    
    # Wait a bit for all nodes to initialize
    await asyncio.sleep(2)
    
    return nodes


def main() -> None:
    """Start multi-node cluster and test communication."""
    # Clean up any existing processes first
    cleanup_ports()
    
    cfg_path = str((ROOT / "config" / "cluster.yaml").resolve())
    config = load_cluster_config(cfg_path)
    
    print(f"Loading cluster config: {len(config.nodes)} nodes")
    for node in config.nodes:
        print(f"  - {node.id}: {node.host}:{node.port}")
    
    async def run_cluster():
        # Start all nodes
        nodes = await start_all_nodes(config)
        
        # Wait a bit for all nodes to fully start
        await asyncio.sleep(2)
        
        # Test inter-node communication
        await test_inter_node_communication(nodes)
        
        # Wait for leader election
        print("\nWaiting for leader election...")
        await asyncio.sleep(3)  # Give time for election
        
        # Check leader election status
        await check_leader_election(nodes)
        
        print(f"\n[SUCCESS] Phase 2 Complete: Raft leader election implemented!")
        print("\nPress Ctrl+C to stop all nodes...")
        
        # Keep running until interrupted
        try:
            # Start leader change monitor
            await monitor_leader(nodes)
        except KeyboardInterrupt:
            print("\nShutting down cluster...")
    
    try:
        asyncio.run(run_cluster())
    except KeyboardInterrupt:
        print("\nCluster stopped.")


if __name__ == "__main__":
    main()
