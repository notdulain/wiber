"""Tests for the message deduplication system."""

import pytest
import time
from src.replication.dedup import MessageDeduplicator


class TestMessageDeduplicator:
    def test_initialization(self):
        """Test deduplicator initialization."""
        dedup = MessageDeduplicator(cache_size=1000, ttl_seconds=60)
        
        assert dedup.cache_size == 1000
        assert dedup.ttl_seconds == 60
        assert dedup.total_messages_processed == 0
        assert dedup.duplicate_messages_detected == 0
        assert len(dedup.message_cache) == 0
        assert len(dedup.topic_caches) == 0
    
    def test_generate_message_id(self):
        """Test message ID generation."""
        dedup = MessageDeduplicator()
        
        message1 = {"key": "value1", "data": "test data"}
        message2 = {"key": "value2", "data": "test data"}
        message3 = {"key": "value1", "data": "test data"}  # Same as message1
        
        id1 = dedup.generate_message_id(message1, "topic1")
        id2 = dedup.generate_message_id(message2, "topic1")
        id3 = dedup.generate_message_id(message3, "topic1")
        
        # Different messages should have different IDs
        assert id1 != id2
        # Same message should have same ID
        assert id1 == id3
        
        # Same message in different topics should have different IDs
        id4 = dedup.generate_message_id(message1, "topic2")
        assert id1 != id4
        
        # IDs should be consistent (deterministic)
        id1_again = dedup.generate_message_id(message1, "topic1")
        assert id1 == id1_again
    
    def test_duplicate_detection(self):
        """Test duplicate message detection."""
        dedup = MessageDeduplicator()
        
        message = {"key": "value", "data": "test"}
        
        # First time should not be duplicate
        assert not dedup.is_duplicate(message, "topic1")
        
        # Add message to cache
        dedup.add_message(message, "topic1")
        
        # Second time should be duplicate
        assert dedup.is_duplicate(message, "topic1")
        
        # Same message in different topic should not be duplicate
        assert not dedup.is_duplicate(message, "topic2")
    
    def test_add_message(self):
        """Test adding messages to cache."""
        dedup = MessageDeduplicator()
        
        message = {"key": "value", "data": "test"}
        
        # Add message
        message_id = dedup.add_message(message, "topic1")
        
        # Check that message ID is generated
        assert message_id is not None
        assert len(message_id) == 64  # SHA-256 hex length
        
        # Check statistics
        assert dedup.total_messages_processed == 1
        assert dedup.duplicate_messages_detected == 0
        
        # Check cache
        assert len(dedup.message_cache) == 1
        assert "topic1" in dedup.topic_caches
        assert len(dedup.topic_caches["topic1"]) == 1
    
    def test_cache_stats(self):
        """Test cache statistics."""
        dedup = MessageDeduplicator()
        
        # Add some messages
        dedup.add_message({"key": "value1"}, "topic1")
        dedup.add_message({"key": "value2"}, "topic1")
        dedup.add_message({"key": "value3"}, "topic2")
        
        # Check duplicate
        dedup.is_duplicate({"key": "value1"}, "topic1")
        
        stats = dedup.get_cache_stats()
        
        assert stats["total_messages_processed"] == 3
        assert stats["duplicate_messages_detected"] == 1
        assert stats["duplicate_rate"] == 1/3
        assert stats["cache_size"] == 3
        assert stats["active_entries"] == 3
        assert stats["topic_stats"]["topic1"] == 2
        assert stats["topic_stats"]["topic2"] == 1
    
    def test_ttl_expiration(self):
        """Test TTL-based cache expiration."""
        dedup = MessageDeduplicator(ttl_seconds=0.1)  # Very short TTL
        
        message = {"key": "value", "data": "test"}
        
        # Add message
        dedup.add_message(message, "topic1")
        
        # Should be duplicate immediately
        assert dedup.is_duplicate(message, "topic1")
        
        # Wait for TTL to expire
        time.sleep(0.2)
        
        # Should not be duplicate after TTL expires
        assert not dedup.is_duplicate(message, "topic1")
    
    def test_cache_size_limit(self):
        """Test cache size limit enforcement."""
        dedup = MessageDeduplicator(cache_size=3)
        
        # Add more messages than cache size
        for i in range(5):
            dedup.add_message({"key": f"value{i}"}, "topic1")
        
        # Cache should not exceed size limit
        assert len(dedup.message_cache) <= 3
        
        # Statistics should still be accurate
        assert dedup.total_messages_processed == 5
    
    def test_clear_cache(self):
        """Test cache clearing."""
        dedup = MessageDeduplicator()
        
        # Add messages
        dedup.add_message({"key": "value1"}, "topic1")
        dedup.add_message({"key": "value2"}, "topic2")
        
        assert len(dedup.message_cache) == 2
        assert len(dedup.topic_caches) == 2
        
        # Clear specific topic
        dedup.clear_cache("topic1")
        
        assert len(dedup.message_cache) == 2  # Global cache unchanged
        assert "topic1" not in dedup.topic_caches
        assert "topic2" in dedup.topic_caches
        
        # Clear all cache
        dedup.clear_cache()
        
        assert len(dedup.message_cache) == 0
        assert len(dedup.topic_caches) == 0
    
    def test_is_message_id_cached(self):
        """Test checking if specific message ID is cached."""
        dedup = MessageDeduplicator()
        
        message = {"key": "value", "data": "test"}
        message_id = dedup.add_message(message, "topic1")
        
        # Should be cached
        assert dedup.is_message_id_cached(message_id, "topic1")
        
        # Different message ID should not be cached
        different_id = "different_message_id"
        assert not dedup.is_message_id_cached(different_id, "topic1")
    
    def test_get_cached_message_ids(self):
        """Test getting cached message IDs."""
        dedup = MessageDeduplicator()
        
        # Add messages to different topics
        message1 = {"key": "value1"}
        message2 = {"key": "value2"}
        message3 = {"key": "value3"}
        
        id1 = dedup.add_message(message1, "topic1")
        id2 = dedup.add_message(message2, "topic1")
        id3 = dedup.add_message(message3, "topic2")
        
        # Get all cached IDs
        all_ids = dedup.get_cached_message_ids()
        assert len(all_ids) == 3
        assert id1 in all_ids
        assert id2 in all_ids
        assert id3 in all_ids
        
        # Get topic-specific IDs
        topic1_ids = dedup.get_cached_message_ids("topic1")
        assert len(topic1_ids) == 2
        assert id1 in topic1_ids
        assert id2 in topic1_ids
        assert id3 not in topic1_ids
        
        topic2_ids = dedup.get_cached_message_ids("topic2")
        assert len(topic2_ids) == 1
        assert id3 in topic2_ids
    
    def test_different_message_types(self):
        """Test deduplication with different message types."""
        dedup = MessageDeduplicator()
        
        # Test with different data types
        messages = [
            {"string": "hello"},
            {"number": 42},
            {"boolean": True},
            {"list": [1, 2, 3]},
            {"nested": {"key": "value"}},
            {"null": None}
        ]
        
        for i, message in enumerate(messages):
            # First time should not be duplicate
            assert not dedup.is_duplicate(message, "test")
            
            # Add to cache
            dedup.add_message(message, "test")
            
            # Second time should be duplicate
            assert dedup.is_duplicate(message, "test")
        
        assert dedup.total_messages_processed == len(messages)
        assert dedup.duplicate_messages_detected == len(messages)
    
    def test_edge_cases(self):
        """Test edge cases."""
        dedup = MessageDeduplicator()
        
        # Empty message
        empty_message = {}
        assert not dedup.is_duplicate(empty_message, "test")
        dedup.add_message(empty_message, "test")
        assert dedup.is_duplicate(empty_message, "test")
        
        # Very large message
        large_message = {"data": "x" * 10000}
        assert not dedup.is_duplicate(large_message, "test")
        dedup.add_message(large_message, "test")
        assert dedup.is_duplicate(large_message, "test")
        
        # Special characters
        special_message = {"key": "special chars: !@#$%^&*()"}
        assert not dedup.is_duplicate(special_message, "test")
        dedup.add_message(special_message, "test")
        assert dedup.is_duplicate(special_message, "test")
