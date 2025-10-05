"""Tests for commit log with deduplication integration."""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from src.replication.log import CommitLog


class TestCommitLogDeduplication:
    def setup_method(self):
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)
    
    def test_deduplication_enabled(self):
        """Test that deduplication is enabled by default."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        assert log.deduplicator is not None
        assert log.deduplicator.topic_caches["test-topic"] is not None
    
    def test_deduplication_disabled(self):
        """Test that deduplication can be disabled."""
        log = CommitLog(str(self.log_dir), "test-topic", enable_dedup=False)
        
        assert log.deduplicator is None
    
    def test_duplicate_detection(self):
        """Test that duplicate messages are detected and not stored."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        message = {"key": "value", "data": "test"}
        
        # First append should succeed
        offset1 = log.append(message)
        assert offset1 == 0
        assert log.get_entry_count() == 1
        
        # Second append should be detected as duplicate
        offset2 = log.append(message)
        assert offset2 == -1  # Indicates duplicate
        assert log.get_entry_count() == 1  # No new entry added
        
        # Different message should be added
        different_message = {"key": "different", "data": "test"}
        offset3 = log.append(different_message)
        assert offset3 == 1
        assert log.get_entry_count() == 2
    
    def test_deduplication_without_dedup(self):
        """Test that duplicates are allowed when deduplication is disabled."""
        log = CommitLog(str(self.log_dir), "test-topic", enable_dedup=False)
        
        message = {"key": "value", "data": "test"}
        
        # Both appends should succeed
        offset1 = log.append(message)
        offset2 = log.append(message)
        
        assert offset1 == 0
        assert offset2 == 1
        assert log.get_entry_count() == 2
    
    def test_deduplication_stats(self):
        """Test that deduplication statistics are included in log info."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        message = {"key": "value", "data": "test"}
        
        # Add message
        log.append(message)
        
        # Try to add duplicate
        log.append(message)
        
        # Get log info
        info = log.get_log_info()
        
        assert info["deduplication_enabled"] is True
        assert "deduplication_stats" in info
        
        dedup_stats = info["deduplication_stats"]
        assert dedup_stats["total_messages_processed"] == 1
        assert dedup_stats["duplicate_messages_detected"] == 1
        assert dedup_stats["duplicate_rate"] == 1.0
    
    def test_different_topics_deduplication(self):
        """Test that same message in different topics is not considered duplicate."""
        log1 = CommitLog(str(self.log_dir), "topic1")
        log2 = CommitLog(str(self.log_dir), "topic2")
        
        message = {"key": "value", "data": "test"}
        
        # Add to both topics
        offset1 = log1.append(message)
        offset2 = log2.append(message)
        
        assert offset1 == 0
        assert offset2 == 0
        assert log1.get_entry_count() == 1
        assert log2.get_entry_count() == 1
    
    def test_deduplication_cache_cleanup(self):
        """Test that deduplication cache cleanup works."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Set a very short TTL for testing
        log.deduplicator.ttl_seconds = 0.1
        
        message = {"key": "value", "data": "test"}
        
        # First append
        offset1 = log.append(message)
        assert offset1 == 0
        
        # Should be duplicate immediately
        offset2 = log.append(message)
        assert offset2 == -1
        
        # Wait for TTL to expire
        time.sleep(0.2)
        
        # Should not be duplicate after TTL expires
        offset3 = log.append(message)
        assert offset3 == 1
    
    def test_deduplication_with_complex_messages(self):
        """Test deduplication with complex message structures."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        complex_message = {
            "user": {
                "id": 123,
                "name": "Alice",
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "action": "login",
            "timestamp": 1234567890,
            "metadata": ["tag1", "tag2", "tag3"]
        }
        
        # First append
        offset1 = log.append(complex_message)
        assert offset1 == 0
        
        # Should be duplicate
        offset2 = log.append(complex_message)
        assert offset2 == -1
        
        # Slightly different message should not be duplicate
        different_message = complex_message.copy()
        different_message["user"]["id"] = 456
        
        offset3 = log.append(different_message)
        assert offset3 == 1
    
    def test_deduplication_performance(self):
        """Test deduplication performance with many messages."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add many unique messages
        for i in range(100):
            message = {"id": i, "data": f"message_{i}"}
            offset = log.append(message)
            assert offset == i
        
        assert log.get_entry_count() == 100
        
        # Try to add duplicates
        duplicates_detected = 0
        for i in range(100):
            message = {"id": i, "data": f"message_{i}"}
            offset = log.append(message)
            if offset == -1:
                duplicates_detected += 1
        
        assert duplicates_detected == 100
        assert log.get_entry_count() == 100  # No new entries
    
    def test_deduplication_edge_cases(self):
        """Test deduplication with edge cases."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Empty message
        empty_message = {}
        offset1 = log.append(empty_message)
        offset2 = log.append(empty_message)
        
        assert offset1 == 0
        assert offset2 == -1
        
        # Message with None values
        none_message = {"key": None, "value": "test"}
        offset3 = log.append(none_message)
        offset4 = log.append(none_message)
        
        assert offset3 == 1
        assert offset4 == -1
        
        # Message with special characters
        special_message = {"key": "special: !@#$%^&*()", "value": "test"}
        offset5 = log.append(special_message)
        offset6 = log.append(special_message)
        
        assert offset5 == 2
        assert offset6 == -1
