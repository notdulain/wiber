#!/usr/bin/env python3
"""
Time Synchronization Demonstration Script

This script demonstrates various time synchronization scenarios:
1. Clock skew simulation
2. Physical vs logical clock ordering
3. NTP synchronization
4. Message ordering analysis
"""

import time
import json
import argparse
import threading
import os
import sys
from typing import List, Dict

# Allow running this file directly (python3 src/demos/time_sync_demo.py)
# by appending the project root (two levels up from this file) to sys.path
try:
    from src.utils.time_sync import (
        TimeSyncConfig, TimeSynchronizer, ClockType,
        simulate_clock_skew, get_time_sync, VectorClock,
    )
except ModuleNotFoundError:
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.utils.time_sync import (
        TimeSyncConfig, TimeSynchronizer, ClockType,
        simulate_clock_skew, get_time_sync, VectorClock,
    )


def simulate_distributed_system():
    """Simulate a distributed system with clock skew"""
    print("=== DISTRIBUTED SYSTEM CLOCK SKEW SIMULATION ===\n")
    
    # Create nodes with different clock skews
    nodes = {
        "node-1": {"skew_ms": 0, "drift": 0.0, "random": 0},
        "node-2": {"skew_ms": 100, "drift": 0.1, "random": 5},
        "node-3": {"skew_ms": -50, "drift": -0.05, "random": 3}
    }
    
    messages = []
    
    print("Simulating message exchange with clock skew...")
    print("Node configurations:")
    for node_id, config in nodes.items():
        print(f"  {node_id}: skew={config['skew_ms']}ms, drift={config['drift']}ms/s, random={config['random']}ms")
    print()
    
    # Simulate message exchange
    for i in range(5):
        for node_id, config in nodes.items():
            # Simulate clock skew
            skew = simulate_clock_skew(
                config["skew_ms"], 
                config["drift"], 
                config["random"]
            )
            
            # Create message
            message = {
                "id": f"msg-{i}-{node_id}",
                "node": node_id,
                "content": f"Message {i} from {node_id}",
                "timestamp": time.time(),
                "skew_ms": skew,
                "adjusted_time": time.time() + (skew / 1000.0)
            }
            
            messages.append(message)
            print(f"  {node_id}: {message['content']} (skew: {skew:.1f}ms)")
            
            time.sleep(0.1)  # Small delay between messages
    
    print("\n=== MESSAGE ORDERING ANALYSIS ===")
    
    # Sort by actual time (broker order)
    actual_order = sorted(messages, key=lambda m: m["timestamp"])
    print("Actual chronological order:")
    for i, msg in enumerate(actual_order):
        print(f"  {i+1}. {msg['node']}: {msg['content']} (time: {msg['timestamp']:.3f})")
    
    # Sort by adjusted time (with skew)
    skewed_order = sorted(messages, key=lambda m: m["adjusted_time"])
    print("\nOrder with clock skew applied:")
    for i, msg in enumerate(skewed_order):
        print(f"  {i+1}. {msg['node']}: {msg['content']} (adjusted: {msg['adjusted_time']:.3f})")
    
    # Show ordering differences
    print("\nOrdering differences:")
    for i, (actual, skewed) in enumerate(zip(actual_order, skewed_order)):
        if actual["id"] != skewed["id"]:
            print(f"  Position {i+1}: {actual['node']} -> {skewed['node']}")


def demonstrate_logical_clocks():
    """Demonstrate logical clock ordering"""
    print("\n=== LOGICAL CLOCK DEMONSTRATION ===\n")
    
    config = TimeSyncConfig(logical_clock_enabled=True)
    
    # Create three nodes
    nodes = {
        "alice": TimeSynchronizer(config, "alice"),
        "bob": TimeSynchronizer(config, "bob"),
        "charlie": TimeSynchronizer(config, "charlie")
    }
    
    messages = []
    
    print("Simulating message exchange with logical clocks...")
    
    # Alice sends message 1
    msg1 = nodes["alice"].create_timestamp(ClockType.LOGICAL)
    messages.append(("alice", "Hello from Alice", msg1))
    print(f"Alice sends: {msg1['logical_time']}")
    
    # Bob receives Alice's message and sends his own
    nodes["bob"].update_from_message(msg1)
    msg2 = nodes["bob"].create_timestamp(ClockType.LOGICAL)
    messages.append(("bob", "Hello from Bob", msg2))
    print(f"Bob receives Alice's message and sends: {msg2['logical_time']}")
    
    # Charlie sends message without receiving others
    msg3 = nodes["charlie"].create_timestamp(ClockType.LOGICAL)
    messages.append(("charlie", "Hello from Charlie", msg3))
    print(f"Charlie sends: {msg3['logical_time']}")
    
    # Alice receives Bob's message and sends another
    nodes["alice"].update_from_message(msg2)
    msg4 = nodes["alice"].create_timestamp(ClockType.LOGICAL)
    messages.append(("alice", "Alice's second message", msg4))
    print(f"Alice receives Bob's message and sends: {msg4['logical_time']}")
    
    print("\nLogical clock ordering:")
    for i, (sender, content, timestamp) in enumerate(messages):
        print(f"  {i+1}. {sender}: {content} (logical time: {timestamp['logical_time']})")
    
    print("\nLogical clock states:")
    for node_id, node in nodes.items():
        print(f"  {node_id}: {node.get_logical_time()}")


def demonstrate_ntp_synchronization():
    """Demonstrate NTP synchronization"""
    print("\n=== NTP SYNCHRONIZATION DEMONSTRATION ===\n")
    
    config = TimeSyncConfig(
        ntp_servers=["pool.ntp.org"],
        sync_interval=5.0
    )
    
    sync = TimeSynchronizer(config, "demo-node")
    
    print("Starting NTP synchronization...")
    print("(Note: This may take a few seconds to connect to NTP servers)")
    
    # Start sync in background
    sync.start_sync()
    
    try:
        # Show time before sync
        print(f"Time before sync: {time.time():.3f}")
        
        # Wait for sync
        time.sleep(2)
        
        # Show synchronized time
        synced_time = sync.get_physical_time()
        print(f"Synchronized time: {synced_time:.3f}")
        print(f"Offset: {sync.physical_clock_offset:.3f} seconds")
        
        # Show a few more synchronized timestamps
        print("\nSynchronized timestamps:")
        for i in range(3):
            timestamp = sync.create_timestamp(ClockType.PHYSICAL)
            print(f"  {i+1}. {timestamp['physical_time']:.3f}")
            time.sleep(1)
            
    finally:
        sync.stop_sync()
        print("\nNTP synchronization stopped.")


def demonstrate_vector_clocks():
    """Demonstrate vector clock ordering"""
    print("\n=== VECTOR CLOCK DEMONSTRATION ===\n")
    
    config = TimeSyncConfig(vector_clock_enabled=True)
    
    # Create nodes with vector clocks
    alice = TimeSynchronizer(config, "alice")
    alice.vector_clock = VectorClock("alice", 3)
    
    bob = TimeSynchronizer(config, "bob")
    bob.vector_clock = VectorClock("bob", 3)
    
    charlie = TimeSynchronizer(config, "charlie")
    charlie.vector_clock = VectorClock("charlie", 3)
    
    print("Simulating message exchange with vector clocks...")
    
    # Alice sends message
    msg1 = alice.create_timestamp(ClockType.VECTOR)
    print(f"Alice sends: {msg1['vector_time']}")
    
    # Bob receives and sends
    bob.update_from_message(msg1)
    msg2 = bob.create_timestamp(ClockType.VECTOR)
    print(f"Bob receives Alice's message and sends: {msg2['vector_time']}")
    
    # Charlie sends without receiving
    msg3 = charlie.create_timestamp(ClockType.VECTOR)
    print(f"Charlie sends: {msg3['vector_time']}")
    
    # Alice receives Bob's message
    alice.update_from_message(msg2)
    msg4 = alice.create_timestamp(ClockType.VECTOR)
    print(f"Alice receives Bob's message and sends: {msg4['vector_time']}")
    
    print("\nVector clock relationships:")
    print(f"Alice's final clock: {alice.get_vector_time()}")
    print(f"Bob's final clock: {bob.get_vector_time()}")
    print(f"Charlie's final clock: {charlie.get_vector_time()}")
    
    # Show causal relationships
    print("\nCausal relationships:")
    print(f"msg1 -> msg2: {alice.vector_clock.compare(msg2['vector_time'])}")
    print(f"msg1 -> msg3: {alice.vector_clock.compare(msg3['vector_time'])}")
    print(f"msg2 -> msg4: {bob.vector_clock.compare(msg4['vector_time'])}")


def main():
    parser = argparse.ArgumentParser(description="Time Synchronization Demonstration")
    parser.add_argument("--demo", choices=["skew", "logical", "ntp", "vector", "all"], 
                       default="all", help="Which demonstration to run")
    parser.add_argument("--ntp-timeout", type=int, default=10, 
                       help="NTP synchronization timeout in seconds")
    
    args = parser.parse_args()
    
    print("Time Synchronization Demonstration")
    print("=" * 50)
    
    if args.demo in ["skew", "all"]:
        simulate_distributed_system()
    
    if args.demo in ["logical", "all"]:
        demonstrate_logical_clocks()
    
    if args.demo in ["ntp", "all"]:
        try:
            demonstrate_ntp_synchronization()
        except Exception as e:
            print(f"NTP demonstration failed: {e}")
            print("This is normal if NTP servers are not accessible.")
    
    if args.demo in ["vector", "all"]:
        demonstrate_vector_clocks()
    
    print("\n" + "=" * 50)
    print("Demonstration complete!")


if __name__ == "__main__":
    main()
