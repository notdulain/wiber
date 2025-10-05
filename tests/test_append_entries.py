"""Tests for AppendEntries RPC functionality."""

import pytest
import time
from src.cluster.raft import Raft, RaftState


class TestAppendEntries:
    def test_append_entries_heartbeat(self):
        """Test that AppendEntries works as heartbeat."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.state = RaftState.FOLLOWER
        
        # Send heartbeat (empty entries)
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        
        assert response["term"] == 1
        assert response["success"] is True
        assert raft.last_heartbeat > time.time() - 1  # Should be recent

    def test_append_entries_term_update(self):
        """Test that AppendEntries updates term if leader has higher term."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.state = RaftState.CANDIDATE
        
        # Send AppendEntries with higher term
        response = raft.handle_append_entries(
            leader_id="n2",
            term=2,
            prev_log_index=0,
            prev_log_term=0,
            entries=[],
            leader_commit=0
        )
        
        assert response["term"] == 2
        assert response["success"] is True
        assert raft.current_term == 2
        assert raft.state == RaftState.FOLLOWER
        assert raft.voted_for is None

    def test_append_entries_log_consistency_success(self):
        """Test successful log consistency check."""
        raft = Raft("n1")
        raft.current_term = 1
        
        # Add some entries to the log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Send AppendEntries that should succeed
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=2,  # We have 2 entries
            prev_log_term=1,   # Last entry has term 1
            entries=[{"term": 1, "command": "SET", "key": "z", "value": "3"}],
            leader_commit=2
        )
        
        assert response["success"] is True
        assert len(raft.log) == 3
        assert raft.log[2]["command"] == "SET"
        assert raft.log[2]["key"] == "z"

    def test_append_entries_log_consistency_failure(self):
        """Test failed log consistency check."""
        raft = Raft("n1")
        raft.current_term = 1
        
        # Add some entries to the log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Send AppendEntries with wrong prev_log_term
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=2,  # We have 2 entries
            prev_log_term=2,   # But last entry has term 1, not 2
            entries=[{"term": 1, "command": "SET", "key": "z", "value": "3"}],
            leader_commit=2
        )
        
        assert response["success"] is False
        assert len(raft.log) == 2  # Log should be unchanged

    def test_append_entries_log_too_short(self):
        """Test AppendEntries when follower log is too short."""
        raft = Raft("n1")
        raft.current_term = 1
        
        # Add only one entry to the log
        raft.log = [{"term": 1, "command": "SET", "key": "x", "value": "1"}]
        
        # Send AppendEntries asking for prev_log_index=3 (we only have 1)
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=3,  # We only have 1 entry
            prev_log_term=1,
            entries=[{"term": 1, "command": "SET", "key": "z", "value": "3"}],
            leader_commit=1
        )
        
        assert response["success"] is False
        assert len(raft.log) == 1  # Log should be unchanged

    def test_append_entries_conflict_resolution(self):
        """Test that AppendEntries removes conflicting entries."""
        raft = Raft("n1")
        raft.current_term = 1
        
        # Add entries to the log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"},
            {"term": 1, "command": "SET", "key": "z", "value": "3"}
        ]
        
        # Send AppendEntries that conflicts at index 2
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=2,  # Keep first 2 entries
            prev_log_term=1,   # Last kept entry has term 1
            entries=[
                {"term": 2, "command": "SET", "key": "a", "value": "4"},
                {"term": 2, "command": "SET", "key": "b", "value": "5"}
            ],
            leader_commit=2
        )
        
        assert response["success"] is True
        assert len(raft.log) == 4  # 2 kept + 2 new
        assert raft.log[2]["key"] == "a"  # New entry
        assert raft.log[3]["key"] == "b"  # New entry
        # The old "z" entry should be gone

    def test_append_entries_commit_index_update(self):
        """Test that AppendEntries updates commit index."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.commit_index = 0
        
        # Add entries to the log
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
        ]
        
        # Send AppendEntries with leader_commit=1
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=2,
            prev_log_term=1,
            entries=[],
            leader_commit=1
        )
        
        assert response["success"] is True
        assert raft.commit_index == 1

    def test_append_entries_commit_index_capped(self):
        """Test that commit index is capped by log length."""
        raft = Raft("n1")
        raft.current_term = 1
        raft.commit_index = 0
        
        # Add only one entry to the log
        raft.log = [{"term": 1, "command": "SET", "key": "x", "value": "1"}]
        
        # Send AppendEntries with leader_commit=5 (more than we have)
        response = raft.handle_append_entries(
            leader_id="n2",
            term=1,
            prev_log_index=1,
            prev_log_term=1,
            entries=[],
            leader_commit=5  # More than log length
        )
        
        assert response["success"] is True
        assert raft.commit_index == 1  # Should be capped at log length
