#!/usr/bin/env python3
"""Helper to start a local multi-node cluster with time synchronization."""

import time
import threading
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.time.lamport import MessageOrdering
from src.time.sync import TimeSyncServer, TimeSyncClient, TimeSyncConfig


class SimpleNode:
    """Simple node implementation with time synchronization."""
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        self.message_ordering = MessageOrdering(node_id, use_vector_clocks=False)
        self.time_sync_server = TimeSyncServer(node_id, port=port)
        self.time_sync_client = TimeSyncClient(node_id)
        self.running = False
    
    def start(self):
        """Start the node."""
        print(f"Starting node {self.node_id} on port {self.port}")
        
        # Start time sync server
        self.time_sync_server.start()
        
        # Start time sync client (will sync with other nodes)
        peers = [
            ("127.0.0.1", 9101, "n1"),
            ("127.0.0.1", 9102, "n2"),
            ("127.0.0.1", 9103, "n3")
        ]
        # Remove self from peers
        peers = [p for p in peers if p[1] != self.port]
        
        if peers:
            self.time_sync_client.start_background_sync(peers)
        
        self.running = True
        print(f"Node {self.node_id} started successfully")
    
    def stop(self):
        """Stop the node."""
        print(f"Stopping node {self.node_id}")
        self.running = False
        self.time_sync_server.stop()
        self.time_sync_client.stop_background_sync()
    
    def send_message(self, content: str):
        """Send a message with time synchronization."""
        timestamp = self.message_ordering.create_timestamp()
        message = {
            "node_id": self.node_id,
            "content": content,
            "timestamp": timestamp
        }
        
        print(f"[{self.node_id}] Sending: {content}")
        print(f"  Logical time: {timestamp['logical_time']}")
        print(f"  Physical time: {timestamp['physical_time']:.6f}")
        
        return message
    
    def receive_message(self, message: dict):
        """Receive and process a message."""
        print(f"[{self.node_id}] Received from {message['node_id']}: {message['content']}")
        
        # Update our clocks based on received message
        new_timestamp = self.message_ordering.update_from_message(message['timestamp'])
        
        print(f"  Updated logical time: {new_timestamp['logical_time']}")
        print(f"  Current physical time: {new_timestamp['physical_time']:.6f}")
        
        return new_timestamp


def simulate_message_exchange():
    """Simulate message exchange between nodes."""
    print("=== Simulating Message Exchange ===\n")
    
    # Create nodes
    nodes = {
        "n1": SimpleNode("n1", 9101),
        "n2": SimpleNode("n2", 9102),
        "n3": SimpleNode("n3", 9103)
    }
    
    try:
        # Start all nodes
        for node in nodes.values():
            node.start()
            time.sleep(0.1)  # Small delay between starts
        
        print("\nAll nodes started. Waiting for time sync...")
        time.sleep(2)  # Let time sync stabilize
        
        # Simulate message exchange
        print("\n--- Message Exchange Simulation ---")
        
        # Node 1 sends message
        msg1 = nodes["n1"].send_message("Hello from node 1")
        time.sleep(0.1)
        
        # Node 2 receives and sends
        nodes["n2"].receive_message(msg1)
        msg2 = nodes["n2"].send_message("Hello from node 2")
        time.sleep(0.1)
        
        # Node 3 sends without receiving
        msg3 = nodes["n3"].send_message("Hello from node 3")
        time.sleep(0.1)
        
        # Node 1 receives node 2's message
        nodes["n1"].receive_message(msg2)
        msg4 = nodes["n1"].send_message("Node 1's second message")
        
        print("\n--- Final States ---")
        for node_id, node in nodes.items():
            current_time = node.message_ordering.get_current_time()
            print(f"{node_id}: logical_time={current_time['logical_time']}")
        
    finally:
        # Stop all nodes
        print("\nStopping all nodes...")
        for node in nodes.values():
            node.stop()


def main():
    """Main function."""
    print("Wiber Distributed System - Time Synchronization Demo")
    print("=" * 60)
    
    try:
        simulate_message_exchange()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\nDemo complete!")


if __name__ == "__main__":
    main()

