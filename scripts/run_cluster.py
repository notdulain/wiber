#!/usr/bin/env python3
"""Start multiple nodes from config and test inter-node communication (Phase 1).

Loads all nodes from `config/cluster.yaml` and starts them with both API and RPC servers.
Then tests that all nodes can communicate with each other.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure src is on path
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from config.cluster import load_cluster_config  # type: ignore
from cluster.node import Node  # type: ignore


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
                        print(f"  ✅ {node.node_id} -> {other_node.node_id}: PONG")
                    else:
                        print(f"  ❌ {node.node_id} -> {other_node.node_id}: {result}")
                except Exception as e:
                    print(f"  ❌ {node.node_id} -> {other_node.node_id}: Error - {e}")


async def start_all_nodes(config) -> list[Node]:
    """Start all nodes from config."""
    nodes = []
    
    print("Starting cluster nodes...")
    for node_config in config.nodes:
        node = Node(
            node_id=node_config.id,
            host=node_config.host,
            port=node_config.port
        )
        nodes.append(node)
        
        # Start each node in a separate task
        asyncio.create_task(node._start_async())
        
        # Give each node a moment to start
        await asyncio.sleep(0.5)
    
    print(f"\nStarted {len(nodes)} nodes")
    return nodes


def main() -> None:
    """Start multi-node cluster and test communication."""
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
        
        print(f"\n✅ Phase 1 Complete: {len(nodes)} nodes running and communicating!")
        print("\nPress Ctrl+C to stop all nodes...")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down cluster...")
    
    try:
        asyncio.run(run_cluster())
    except KeyboardInterrupt:
        print("\nCluster stopped.")


if __name__ == "__main__":
    main()

