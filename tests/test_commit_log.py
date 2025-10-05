"""Tests for the commit log implementation."""

import pytest
import tempfile
import shutil
import json
import time
from pathlib import Path
from src.replication.log import CommitLog


class TestCommitLog:
    def setup_method(self):
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_fresh_log(self):
        """Test creating a new commit log."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        assert log.topic == "test-topic"
        assert log.get_entry_count() == 0
        assert log.get_latest_offset() == -1
        assert log.next_offset == 0
        
        # Log file is created when first message is appended
        log_file = self.log_dir / "test-topic.log"
        assert not log_file.exists()  # Should not exist yet
        
        # Add a message to create the file
        log.append({"key": "value", "data": "test"})
        assert log_file.exists()  # Now it should exist
    
    def test_append_message(self):
        """Test appending messages to the log."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Append first message
        message1 = {"key": "value1", "data": "test data 1"}
        offset1 = log.append(message1)
        
        assert offset1 == 0
        assert log.get_entry_count() == 1
        assert log.get_latest_offset() == 0
        
        # Append second message
        message2 = {"key": "value2", "data": "test data 2"}
        offset2 = log.append(message2)
        
        assert offset2 == 1
        assert log.get_entry_count() == 2
        assert log.get_latest_offset() == 1
    
    def test_read_messages(self):
        """Test reading messages from the log."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add some messages
        messages = [
            {"key": "value1", "data": "test data 1"},
            {"key": "value2", "data": "test data 2"},
            {"key": "value3", "data": "test data 3"}
        ]
        
        offsets = []
        for message in messages:
            offset = log.append(message)
            offsets.append(offset)
        
        # Read all messages
        entries = log.read()
        assert len(entries) == 3
        
        for i, entry in enumerate(entries):
            assert entry['offset'] == i
            assert entry['topic'] == "test-topic"
            assert entry['message'] == messages[i]
            assert 'timestamp' in entry
        
        # Read with offset
        entries_from_offset = log.read(offset=1)
        assert len(entries_from_offset) == 2
        assert entries_from_offset[0]['offset'] == 1
        assert entries_from_offset[1]['offset'] == 2
        
        # Read with limit
        entries_with_limit = log.read(limit=2)
        assert len(entries_with_limit) == 2
        assert entries_with_limit[0]['offset'] == 0
        assert entries_with_limit[1]['offset'] == 1
    
    def test_read_range(self):
        """Test reading messages in a specific range."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add some messages
        for i in range(5):
            log.append({"key": f"value{i}", "data": f"test data {i}"})
        
        # Read range
        entries = log.read_range(1, 4)
        assert len(entries) == 3
        assert entries[0]['offset'] == 1
        assert entries[1]['offset'] == 2
        assert entries[2]['offset'] == 3
    
    def test_persistence(self):
        """Test that messages persist across log restarts."""
        # Create first log instance
        log1 = CommitLog(str(self.log_dir), "test-topic")
        
        # Add some messages
        messages = [
            {"key": "value1", "data": "persistent data 1"},
            {"key": "value2", "data": "persistent data 2"}
        ]
        
        for message in messages:
            log1.append(message)
        
        # Close first log
        log1.close()
        
        # Create second log instance (should load existing data)
        log2 = CommitLog(str(self.log_dir), "test-topic")
        
        # Check that messages were loaded
        assert log2.get_entry_count() == 2
        assert log2.get_latest_offset() == 1
        
        entries = log2.read()
        assert len(entries) == 2
        assert entries[0]['message'] == messages[0]
        assert entries[1]['message'] == messages[1]
        
        # Add more messages
        log2.append({"key": "value3", "data": "new data"})
        assert log2.get_entry_count() == 3
    
    def test_truncate(self):
        """Test truncating the log."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add some messages
        for i in range(5):
            log.append({"key": f"value{i}", "data": f"test data {i}"})
        
        assert log.get_entry_count() == 5
        
        # Truncate at offset 2
        log.truncate(2)
        
        assert log.get_entry_count() == 2
        assert log.get_latest_offset() == 1
        assert log.next_offset == 2
        
        # Check remaining entries
        entries = log.read()
        assert len(entries) == 2
        assert entries[0]['offset'] == 0
        assert entries[1]['offset'] == 1
    
    def test_log_info(self):
        """Test getting log information."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add some messages
        log.append({"key": "value1", "data": "test data"})
        log.append({"key": "value2", "data": "test data"})
        
        info = log.get_log_info()
        
        assert info['topic'] == "test-topic"
        assert info['entries_count'] == 2
        assert info['next_offset'] == 2
        assert info['latest_offset'] == 1
        assert info['log_size_bytes'] > 0
        assert 'log_file' in info
    
    def test_multiple_topics(self):
        """Test multiple topics in the same directory."""
        log1 = CommitLog(str(self.log_dir), "topic1")
        log2 = CommitLog(str(self.log_dir), "topic2")
        
        # Add messages to both topics
        log1.append({"key": "value1", "data": "topic1 data"})
        log2.append({"key": "value2", "data": "topic2 data"})
        
        # Check that they're separate
        assert log1.get_entry_count() == 1
        assert log2.get_entry_count() == 1
        
        entries1 = log1.read()
        entries2 = log2.read()
        
        assert entries1[0]['topic'] == "topic1"
        assert entries2[0]['topic'] == "topic2"
        assert entries1[0]['message']['data'] == "topic1 data"
        assert entries2[0]['message']['data'] == "topic2 data"
    
    def test_corrupted_log_recovery(self):
        """Test recovery from corrupted log file."""
        log = CommitLog(str(self.log_dir), "test-topic")
        
        # Add a valid message
        log.append({"key": "value1", "data": "valid data"})
        log.close()
        
        # Corrupt the log file by adding invalid JSON
        log_file = self.log_dir / "test-topic.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("invalid json line\n")
            f.write('{"offset": 1, "valid": "json"}\n')
        
        # Create new log instance (should recover)
        log2 = CommitLog(str(self.log_dir), "test-topic")
        
        # Should have loaded the valid entries
        assert log2.get_entry_count() == 2  # 1 original + 1 valid from recovery
        entries = log2.read()
        assert entries[0]['message']['data'] == "valid data"
        assert entries[1]['valid'] == "json"
    
    def test_empty_log_file(self):
        """Test handling of empty log file."""
        # Ensure directory exists first
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = self.log_dir / "empty-topic.log"
        log_file.touch()  # Create empty file
        
        log = CommitLog(str(self.log_dir), "empty-topic")
        
        assert log.get_entry_count() == 0
        assert log.get_latest_offset() == -1
        
        # Should be able to add messages
        log.append({"key": "value", "data": "test"})
        assert log.get_entry_count() == 1
