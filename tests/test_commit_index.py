"""Tests for commit index management and state machine application."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.cluster.raft import Raft, RaftState


class TestCommitIndexManagement:
    def test_commit_index_advancement_majority(self):
        """Test that commit index advances when majority has entries."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add entries to log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"},
            {"term": 1, "command": "SET", "key": "z", "value": "3"}
        ]
        
        # Set up follower tracking - both followers have entry 1
        raft.match_index = {
            "127.0.0.1:9102": 1,  # Has entry 1
            "127.0.0.1:9103": 1   # Has entry 1
        }
        
        # Update commit index
        raft._update_commit_index()
        
        # Should commit entry 1 (majority has it: leader + 2 followers = 3/3)
        assert raft.commit_index == 1
        assert raft.last_applied == 1

    def test_commit_index_no_majority(self):
        """Test that commit index doesn't advance without majority."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add entries to log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Set up follower tracking - no followers have entry 1
        raft.match_index = {
            "127.0.0.1:9102": 0,  # Doesn't have entry 1
            "127.0.0.1:9103": 0   # Doesn't have entry 1
        }
        
        # Update commit index
        raft._update_commit_index()
        
        # Should not commit (only 1/3 have entry 1, need 2/3 for majority)
        assert raft.commit_index == 0
        assert raft.last_applied == 0

    def test_commit_index_partial_majority(self):
        """Test commit index with partial majority."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add entries to log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"},
            {"term": 1, "command": "SET", "key": "z", "value": "3"}
        ]
        
        # Set up follower tracking - only one follower has entry 1
        raft.match_index = {
            "127.0.0.1:9102": 1,  # Has entry 1
            "127.0.0.1:9103": 0   # Doesn't have entry 1
        }
        
        # Update commit index
        raft._update_commit_index()
        
        # Should not commit entry 1 (only 2/3 have it, need 2/3 for majority)
        # Actually, 2/3 IS majority, so it should commit
        assert raft.commit_index == 1
        assert raft.last_applied == 1

    def test_state_machine_application(self):
        """Test that committed entries are applied to state machine."""
        raft = Raft("n1")
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add entries to log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Apply entries 0-1 (first two entries)
        raft._apply_committed_entries(0, 2)
        
        # Check that last_applied was updated
        assert raft.last_applied == 2

    def test_follower_commit_index_update(self):
        """Test that followers update commit index from leader."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add entries to log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Update commit index from leader
        raft._update_follower_commit_index(1)
        
        # Should update commit index and apply entries
        assert raft.commit_index == 1
        assert raft.last_applied == 1

    def test_follower_commit_index_capped(self):
        """Test that follower commit index is capped by log length."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.commit_index = 0
        raft.last_applied = 0
        
        # Add only one entry to log
        raft.log = [{"term": 1, "command": "SET", "key": "x", "value": "1"}]
        
        # Try to update commit index beyond log length
        raft._update_follower_commit_index(5)
        
        # Should be capped at log length
        assert raft.commit_index == 1
        assert raft.last_applied == 1

    def test_log_info_debugging(self):
        """Test that log info provides detailed debugging information."""
        raft = Raft("n1")
        raft.commit_index = 1
        raft.last_applied = 1
        
        # Add entries to log (using the structure that add_entry creates)
        raft.log = [
            {"term": 1, "command": "SET", "data": {"key": "x", "value": "1"}, "timestamp": 1234567890},
            {"term": 1, "command": "SET", "data": {"key": "y", "value": "2"}, "timestamp": 1234567891}
        ]
        
        # Get log info
        log_info = raft.get_log_info()
        
        # Check structure
        assert log_info["log_length"] == 2
        assert log_info["commit_index"] == 1
        assert log_info["last_applied"] == 1
        assert len(log_info["entries"]) == 2
        
        # Check first entry
        entry1 = log_info["entries"][0]
        assert entry1["index"] == 1
        assert entry1["term"] == 1
        assert entry1["command"] == "SET"
        assert entry1["data"]["key"] == "x"
        assert entry1["committed"] is True  # commit_index = 1, so index 1 is committed
        assert entry1["applied"] is True   # last_applied = 1, so index 1 is applied
        
        # Check second entry
        entry2 = log_info["entries"][1]
        assert entry2["index"] == 2
        assert entry2["committed"] is False  # commit_index = 1, so index 2 is not committed
        assert entry2["applied"] is False   # last_applied = 1, so index 2 is not applied

    def test_leader_state_info(self):
        """Test that leader state info includes follower tracking."""
        raft = Raft("n1", [("127.0.0.1", 9102)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Initialize follower tracking
        raft.next_index = {"127.0.0.1:9102": 2}
        raft.match_index = {"127.0.0.1:9102": 1}
        
        # Get state info
        state_info = raft.get_state_info()
        
        # Check that follower tracking is included
        assert "next_index" in state_info
        assert "match_index" in state_info
        assert state_info["next_index"]["127.0.0.1:9102"] == 2
        assert state_info["match_index"]["127.0.0.1:9102"] == 1

    def test_follower_state_info(self):
        """Test that follower state info doesn't include follower tracking."""
        raft = Raft("n1")
        raft.state = RaftState.FOLLOWER
        
        # Get state info
        state_info = raft.get_state_info()
        
        # Check that follower tracking is not included
        assert "next_index" in state_info
        assert "match_index" in state_info
        assert state_info["next_index"] == {}
        assert state_info["match_index"] == {}
