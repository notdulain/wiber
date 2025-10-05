#!/usr/bin/env python3
"""Demonstration script for message deduplication."""

import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from replication.log import CommitLog

def demonstrate_deduplication():
    """Demonstrate message deduplication functionality."""
    print("Message Deduplication Demonstration")
    print("=" * 50)
    
    # Create a commit log with deduplication enabled
    log = CommitLog("demo_data", "demo-topic", enable_dedup=True)
    
    print(f"[OK] Created commit log with deduplication")
    print(f"[OK] Deduplication enabled: {log.deduplicator is not None}")
    
    # Test messages
    test_messages = [
        {"user": "alice", "action": "login", "timestamp": 1234567890},
        {"user": "bob", "action": "login", "timestamp": 1234567891},
        {"user": "alice", "action": "login", "timestamp": 1234567890},  # Duplicate
        {"user": "charlie", "action": "logout", "timestamp": 1234567892},
        {"user": "alice", "action": "login", "timestamp": 1234567890},  # Duplicate again
        {"user": "alice", "action": "logout", "timestamp": 1234567893},  # Different action
    ]
    
    print(f"\nProcessing {len(test_messages)} test messages...")
    
    successful_appends = 0
    duplicates_detected = 0
    
    for i, message in enumerate(test_messages):
        print(f"\nMessage {i+1}: {message}")
        
        offset = log.append(message)
        
        if offset == -1:
            print(f"  [DUPLICATE] Message rejected (duplicate detected)")
            duplicates_detected += 1
        else:
            print(f"  [STORED] Message stored at offset {offset}")
            successful_appends += 1
    
    # Show results
    print(f"\nResults:")
    print(f"  Total messages processed: {len(test_messages)}")
    print(f"  Successfully stored: {successful_appends}")
    print(f"  Duplicates detected: {duplicates_detected}")
    print(f"  Final log entries: {log.get_entry_count()}")
    
    # Show deduplication statistics
    if log.deduplicator:
        stats = log.deduplicator.get_cache_stats()
        print(f"\nDeduplication Statistics:")
        print(f"  Messages processed: {stats['total_messages_processed']}")
        print(f"  Duplicates detected: {stats['duplicate_messages_detected']}")
        print(f"  Duplicate rate: {stats['duplicate_rate']:.2%}")
        print(f"  Cache size: {stats['cache_size']}")
        print(f"  Active entries: {stats['active_entries']}")
    
    # Show log info
    log_info = log.get_log_info()
    print(f"\nLog Information:")
    print(f"  Topic: {log_info['topic']}")
    print(f"  Entries count: {log_info['entries_count']}")
    print(f"  Log file size: {log_info['log_size_bytes']} bytes")
    print(f"  Deduplication enabled: {log_info['deduplication_enabled']}")
    
    # Read back stored messages
    print(f"\nStored Messages:")
    entries = log.read()
    for entry in entries:
        msg = entry['message']
        print(f"  Offset {entry['offset']}: {msg['user']} - {msg['action']}")
    
    print(f"\nDemonstration completed successfully!")
    print(f"Deduplication prevented {duplicates_detected} duplicate messages from being stored!")

if __name__ == "__main__":
    demonstrate_deduplication()
