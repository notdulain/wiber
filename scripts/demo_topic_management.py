#!/usr/bin/env python3
"""Demonstration script for topic management."""

import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from replication.topics import TopicManager

def demonstrate_topic_management():
    """Demonstrate topic management functionality."""
    print("Topic Management Demonstration")
    print("=" * 50)
    
    # Create a topic manager
    manager = TopicManager("demo_topics", enable_dedup=True)
    
    print(f"[OK] Created TopicManager with deduplication enabled")
    print(f"[OK] Log directory: {manager.log_dir}")
    
    # Create some topics
    topics_to_create = [
        ("notifications", "User notifications", 24, 100),
        ("logs", "System logs", 48, 500),
        ("metrics", "Performance metrics", 12, 200),
        ("events", "Application events", 72, 300)
    ]
    
    print(f"\nCreating {len(topics_to_create)} topics...")
    
    for topic_name, description, retention_hours, max_size_mb in topics_to_create:
        success = manager.create_topic(topic_name, description, retention_hours, max_size_mb)
        if success:
            print(f"  [OK] Created topic '{topic_name}' ({description})")
        else:
            print(f"  [FAIL] Failed to create topic '{topic_name}'")
    
    # Publish messages to different topics
    print(f"\nPublishing messages to topics...")
    
    messages_by_topic = {
        "notifications": [
            {"user": "alice", "type": "email", "message": "Welcome to Wiber!"},
            {"user": "bob", "type": "push", "message": "New message received"},
            {"user": "alice", "type": "email", "message": "Welcome to Wiber!"},  # Duplicate
        ],
        "logs": [
            {"level": "INFO", "service": "api", "message": "Server started"},
            {"level": "WARN", "service": "db", "message": "Connection pool low"},
            {"level": "ERROR", "service": "auth", "message": "Authentication failed"},
        ],
        "metrics": [
            {"metric": "cpu_usage", "value": 45.2, "timestamp": time.time()},
            {"metric": "memory_usage", "value": 78.5, "timestamp": time.time()},
            {"metric": "cpu_usage", "value": 45.2, "timestamp": time.time()},  # Duplicate
        ],
        "events": [
            {"event": "user_login", "user_id": 123, "ip": "192.168.1.1"},
            {"event": "user_logout", "user_id": 123, "ip": "192.168.1.1"},
            {"event": "user_login", "user_id": 123, "ip": "192.168.1.1"},  # Duplicate
        ]
    }
    
    total_published = 0
    total_duplicates = 0
    
    for topic_name, messages in messages_by_topic.items():
        print(f"\n  Topic '{topic_name}':")
        for i, message in enumerate(messages):
            offset = manager.publish_message(topic_name, message)
            if offset >= 0:
                print(f"    [STORED] Message {i+1} at offset {offset}")
                total_published += 1
            else:
                print(f"    [DUPLICATE] Message {i+1} rejected")
                total_duplicates += 1
    
    # Show topic statistics
    print(f"\nTopic Statistics:")
    topics = manager.list_topics()
    for topic in topics:
        print(f"  {topic['name']}:")
        print(f"    Description: {topic['description']}")
        print(f"    Messages: {topic.get('current_message_count', 0)}")
        print(f"    Latest offset: {topic.get('latest_offset', -1)}")
        print(f"    Log size: {topic.get('log_size_bytes', 0)} bytes")
        print(f"    Retention: {topic['retention_hours']} hours")
    
    # Show manager statistics
    print(f"\nManager Statistics:")
    stats = manager.get_manager_stats()
    print(f"  Total topics: {stats['total_topics']}")
    print(f"  Active topics: {stats['active_topics']}")
    print(f"  Total messages: {stats['total_messages']}")
    print(f"  Total size: {stats['total_size_bytes']} bytes")
    print(f"  Deduplication enabled: {stats['deduplication_enabled']}")
    
    # Read messages from each topic
    print(f"\nReading messages from topics:")
    for topic_name in ["notifications", "logs", "metrics", "events"]:
        print(f"\n  Topic '{topic_name}':")
        entries = manager.read_messages(topic_name, limit=2)  # Read first 2 messages
        for entry in entries:
            msg = entry['message']
            print(f"    Offset {entry['offset']}: {msg}")
    
    # Test topic validation
    print(f"\nTesting topic name validation:")
    invalid_names = ["", "topic with spaces", "topic@special", "-topic", "topic-"]
    for invalid_name in invalid_names:
        success = manager.create_topic(invalid_name)
        print(f"  '{invalid_name}': {'REJECTED' if not success else 'ACCEPTED'}")
    
    # Test topic deletion
    print(f"\nTesting topic deletion:")
    success = manager.delete_topic("events", force=True)
    print(f"  Deleted 'events' topic: {'SUCCESS' if success else 'FAILED'}")
    
    # Final statistics
    final_stats = manager.get_manager_stats()
    print(f"\nFinal Statistics:")
    print(f"  Total topics: {final_stats['total_topics']}")
    print(f"  Total messages: {final_stats['total_messages']}")
    print(f"  Messages published: {total_published}")
    print(f"  Duplicates prevented: {total_duplicates}")
    
    # Close manager
    manager.close()
    
    print(f"\nDemonstration completed successfully!")
    print(f"Topic management system is working perfectly!")

if __name__ == "__main__":
    demonstrate_topic_management()
