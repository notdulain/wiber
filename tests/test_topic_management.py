"""Tests for the topic management system."""

import pytest
import tempfile
import shutil
import time
import json
from pathlib import Path
from src.replication.topics import TopicManager


class TestTopicManager:
    def setup_method(self):
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test topic manager initialization."""
        manager = TopicManager(str(self.log_dir))
        
        assert manager.log_dir == self.log_dir
        assert manager.enable_dedup is True
        assert len(manager.topics) == 0
        assert len(manager.commit_logs) == 0
        assert manager.metadata_file == self.log_dir / "topics.json"
    
    def test_create_topic(self):
        """Test creating a new topic."""
        manager = TopicManager(str(self.log_dir))
        
        # Create a topic
        success = manager.create_topic(
            "test-topic",
            description="Test topic for unit tests",
            retention_hours=48,
            max_size_mb=200
        )
        
        assert success is True
        assert "test-topic" in manager.topics
        assert "test-topic" in manager.commit_logs
        
        topic_info = manager.topics["test-topic"]
        assert topic_info["name"] == "test-topic"
        assert topic_info["description"] == "Test topic for unit tests"
        assert topic_info["retention_hours"] == 48
        assert topic_info["max_size_mb"] == 200
        assert topic_info["status"] == "active"
        assert topic_info["message_count"] == 0
    
    def test_create_duplicate_topic(self):
        """Test creating a topic that already exists."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic first time
        success1 = manager.create_topic("test-topic")
        assert success1 is True
        
        # Try to create same topic again
        success2 = manager.create_topic("test-topic")
        assert success2 is False
    
    def test_invalid_topic_names(self):
        """Test validation of topic names."""
        manager = TopicManager(str(self.log_dir))
        
        invalid_names = [
            "",  # Empty
            "topic with spaces",  # Spaces
            "topic@with#special",  # Special characters
            "-topic",  # Starts with hyphen
            "_topic",  # Starts with underscore
            "topic-",  # Ends with hyphen
            "topic_",  # Ends with underscore
            "a" * 101,  # Too long
        ]
        
        for invalid_name in invalid_names:
            success = manager.create_topic(invalid_name)
            assert success is False, f"Should reject topic name: {invalid_name}"
    
    def test_valid_topic_names(self):
        """Test valid topic names."""
        manager = TopicManager(str(self.log_dir))
        
        valid_names = [
            "topic",
            "test-topic",
            "test_topic",
            "topic123",
            "topic-123",
            "topic_123",
            "a" * 100,  # Max length
        ]
        
        for valid_name in valid_names:
            success = manager.create_topic(valid_name)
            assert success is True, f"Should accept topic name: {valid_name}"
    
    def test_delete_topic(self):
        """Test deleting a topic."""
        manager = TopicManager(str(self.log_dir))
        
        # Create a topic
        manager.create_topic("test-topic")
        assert "test-topic" in manager.topics
        
        # Delete the topic
        success = manager.delete_topic("test-topic")
        assert success is True
        assert "test-topic" not in manager.topics
        assert "test-topic" not in manager.commit_logs
    
    def test_delete_nonexistent_topic(self):
        """Test deleting a topic that doesn't exist."""
        manager = TopicManager(str(self.log_dir))
        
        success = manager.delete_topic("nonexistent-topic")
        assert success is False
    
    def test_delete_topic_with_messages(self):
        """Test deleting a topic that has messages."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic and add messages
        manager.create_topic("test-topic")
        manager.publish_message("test-topic", {"key": "value"})
        
        # Try to delete without force
        success = manager.delete_topic("test-topic", force=False)
        assert success is False
        
        # Delete with force
        success = manager.delete_topic("test-topic", force=True)
        assert success is True
    
    def test_publish_message(self):
        """Test publishing messages to topics."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic
        manager.create_topic("test-topic")
        
        # Publish message
        message = {"user": "alice", "action": "login"}
        offset = manager.publish_message("test-topic", message)
        
        assert offset == 0
        assert manager.topics["test-topic"]["message_count"] == 1
        assert manager.topics["test-topic"]["last_message_at"] is not None
    
    def test_publish_to_nonexistent_topic(self):
        """Test publishing to a topic that doesn't exist."""
        manager = TopicManager(str(self.log_dir))
        
        message = {"key": "value"}
        offset = manager.publish_message("nonexistent-topic", message)
        
        assert offset == -1
    
    def test_read_messages(self):
        """Test reading messages from a topic."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic and add messages
        manager.create_topic("test-topic")
        
        messages = [
            {"user": "alice", "action": "login"},
            {"user": "bob", "action": "login"},
            {"user": "alice", "action": "logout"}
        ]
        
        for message in messages:
            manager.publish_message("test-topic", message)
        
        # Read all messages
        entries = manager.read_messages("test-topic")
        assert len(entries) == 3
        
        for i, entry in enumerate(entries):
            assert entry["offset"] == i
            assert entry["message"] == messages[i]
    
    def test_read_messages_with_offset_and_limit(self):
        """Test reading messages with offset and limit."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic and add messages
        manager.create_topic("test-topic")
        
        for i in range(5):
            manager.publish_message("test-topic", {"id": i})
        
        # Read with offset
        entries = manager.read_messages("test-topic", offset=2)
        assert len(entries) == 3
        assert entries[0]["offset"] == 2
        
        # Read with limit
        entries = manager.read_messages("test-topic", limit=2)
        assert len(entries) == 2
        assert entries[0]["offset"] == 0
        assert entries[1]["offset"] == 1
    
    def test_list_topics(self):
        """Test listing all topics."""
        manager = TopicManager(str(self.log_dir))
        
        # Create multiple topics
        manager.create_topic("topic1", description="First topic")
        manager.create_topic("topic2", description="Second topic")
        
        # Add messages to one topic
        manager.publish_message("topic1", {"key": "value"})
        
        # List topics
        topics = manager.list_topics()
        assert len(topics) == 2
        
        # Check topic data
        topic1 = next(t for t in topics if t["name"] == "topic1")
        topic2 = next(t for t in topics if t["name"] == "topic2")
        
        assert topic1["description"] == "First topic"
        assert topic1["current_message_count"] == 1
        assert topic2["current_message_count"] == 0
    
    def test_get_topic_info(self):
        """Test getting detailed topic information."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic
        manager.create_topic("test-topic", description="Test topic")
        
        # Add messages
        manager.publish_message("test-topic", {"key": "value"})
        
        # Get topic info
        info = manager.get_topic_info("test-topic")
        
        assert info is not None
        assert info["name"] == "test-topic"
        assert info["description"] == "Test topic"
        assert info["message_count"] == 1
        assert info["entries_count"] == 1
        assert info["deduplication_enabled"] is True
    
    def test_get_nonexistent_topic_info(self):
        """Test getting info for nonexistent topic."""
        manager = TopicManager(str(self.log_dir))
        
        info = manager.get_topic_info("nonexistent-topic")
        assert info is None
    
    def test_topic_metadata_persistence(self):
        """Test that topic metadata persists across restarts."""
        manager1 = TopicManager(str(self.log_dir))
        
        # Create topics
        manager1.create_topic("topic1", description="First topic")
        manager1.create_topic("topic2", description="Second topic")
        
        # Add messages
        manager1.publish_message("topic1", {"key": "value"})
        
        # Close manager
        manager1.close()
        
        # Create new manager (should load existing topics)
        manager2 = TopicManager(str(self.log_dir))
        
        # Check that topics were loaded
        assert len(manager2.topics) == 2
        assert "topic1" in manager2.topics
        assert "topic2" in manager2.topics
        
        # Check that messages were loaded
        entries = manager2.read_messages("topic1")
        assert len(entries) == 1
        assert entries[0]["message"]["key"] == "value"
    
    def test_manager_stats(self):
        """Test getting manager statistics."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topics and add messages
        manager.create_topic("topic1")
        manager.create_topic("topic2")
        
        manager.publish_message("topic1", {"key": "value1"})
        manager.publish_message("topic1", {"key": "value2"})
        manager.publish_message("topic2", {"key": "value3"})
        
        # Get stats
        stats = manager.get_manager_stats()
        
        assert stats["total_topics"] == 2
        assert stats["active_topics"] == 2
        assert stats["total_messages"] == 3
        assert stats["deduplication_enabled"] is True
        assert stats["log_directory"] == str(self.log_dir)
    
    def test_cleanup_expired_topics(self):
        """Test cleanup of expired topics."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topics with different retention periods
        manager.create_topic("short-retention", retention_hours=0.0001)  # Very short (0.36 seconds)
        manager.create_topic("long-retention", retention_hours=24)
        
        # Add messages to both
        manager.publish_message("short-retention", {"key": "value"})
        manager.publish_message("long-retention", {"key": "value"})
        
        # Wait for short retention to expire
        time.sleep(0.5)  # Wait 0.5 seconds (longer than 0.36 seconds)
        
        # Cleanup expired topics
        cleaned_count = manager.cleanup_expired_topics()
        
        assert cleaned_count == 1
        assert "short-retention" not in manager.topics
        assert "long-retention" in manager.topics
    
    def test_deduplication_integration(self):
        """Test that deduplication works with topic management."""
        manager = TopicManager(str(self.log_dir))
        
        # Create topic
        manager.create_topic("test-topic")
        
        message = {"user": "alice", "action": "login"}
        
        # Publish same message twice
        offset1 = manager.publish_message("test-topic", message)
        offset2 = manager.publish_message("test-topic", message)
        
        assert offset1 == 0
        assert offset2 == -1  # Duplicate
        
        # Should only have one message
        entries = manager.read_messages("test-topic")
        assert len(entries) == 1
    
    def test_multiple_topics_isolation(self):
        """Test that topics are isolated from each other."""
        manager = TopicManager(str(self.log_dir))
        
        # Create two topics
        manager.create_topic("topic1")
        manager.create_topic("topic2")
        
        # Add same message to both topics
        message = {"key": "value"}
        
        offset1 = manager.publish_message("topic1", message)
        offset2 = manager.publish_message("topic2", message)
        
        # Both should succeed (different topics)
        assert offset1 == 0
        assert offset2 == 0
        
        # Both topics should have the message
        entries1 = manager.read_messages("topic1")
        entries2 = manager.read_messages("topic2")
        
        assert len(entries1) == 1
        assert len(entries2) == 1
        assert entries1[0]["message"] == entries2[0]["message"]
