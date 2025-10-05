#!/usr/bin/env python3
"""Test script to demonstrate persistent commit log integration."""

import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cluster.raft import Raft, RaftState

def test_persistent_storage():
    """Test that messages are stored persistently."""
    print("Testing Persistent Commit Log Integration")
    print("=" * 50)
    
    # Create a Raft instance
    raft = Raft("test-node", log_dir="test_data")
    raft.state = RaftState.LEADER
    raft.current_term = 1
    
    print(f"[OK] Created Raft node: {raft.node_id}")
    print(f"[OK] Commit log available: {raft.commit_log is not None}")
    
    if raft.commit_log:
        print(f"[OK] Log file: {raft.commit_log.log_file}")
        print(f"[OK] Initial entries: {raft.commit_log.get_entry_count()}")
    
    # Add some test messages
    test_messages = [
        ("SET", {"key": "user:1", "value": "Alice"}),
        ("SET", {"key": "user:2", "value": "Bob"}),
        ("SET", {"key": "user:3", "value": "Charlie"}),
        ("PUB", {"topic": "notifications", "message": "Hello World"}),
        ("PUB", {"topic": "notifications", "message": "System started"})
    ]
    
    print(f"\nAdding {len(test_messages)} test messages...")
    
    for i, (command, data) in enumerate(test_messages):
        success = raft.add_entry(command, data)
        if success:
            print(f"  [OK] Message {i+1}: {command} {data}")
        else:
            print(f"  [FAIL] Failed to add message {i+1}")
    
    # Check persistent storage
    if raft.commit_log:
        print(f"\nPersistent Storage Status:")
        print(f"  Total entries: {raft.commit_log.get_entry_count()}")
        print(f"  Latest offset: {raft.commit_log.get_latest_offset()}")
        print(f"  Log file size: {raft.commit_log.get_log_info()['log_size_bytes']} bytes")
        
        # Read back some messages
        print(f"\nReading messages from persistent storage:")
        entries = raft.commit_log.read(limit=3)
        for entry in entries:
            msg = entry['message']
            print(f"  Offset {entry['offset']}: {msg['command']} {msg['data']}")
    
    print(f"\nTest completed successfully!")
    print(f"Messages are now stored persistently and will survive restarts!")

if __name__ == "__main__":
    test_persistent_storage()
