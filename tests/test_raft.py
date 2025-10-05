"""Tests for Raft consensus algorithm."""

import sys
from pathlib import Path
import time

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pytest

from cluster.raft import Raft, RaftState  # noqa: E402


class TestRaftState:
    """Test Raft state management."""
    
    def test_initial_state(self):
        """Test that Raft starts in correct initial state."""
        raft = Raft("test-node")
        
        assert raft.node_id == "test-node"
        assert raft.state == RaftState.FOLLOWER
        assert raft.current_term == 0
        assert raft.voted_for is None
        assert raft.commit_index == 0
        assert raft.last_applied == 0
        assert len(raft.log) == 0
    
    def test_state_transitions(self):
        """Test basic state transitions."""
        raft = Raft("test-node")
        
        # Start as follower
        assert raft.state == RaftState.FOLLOWER
        
        # Manually transition to candidate (simulating election timeout)
        raft._start_election()
        assert raft.state == RaftState.CANDIDATE
        assert raft.current_term == 1
        assert raft.voted_for == "test-node"
    
    def test_request_vote_granting(self):
        """Test RequestVote RPC vote granting logic."""
        raft = Raft("test-node")
        
        # Grant vote to candidate with higher term
        response = raft.handle_request_vote("candidate", 1, 0, 0)
        
        assert response["term"] == 1
        assert response["vote_granted"] is True
        assert raft.voted_for == "candidate"
        assert raft.current_term == 1
        assert raft.state == RaftState.FOLLOWER
    
    def test_request_vote_denial(self):
        """Test RequestVote RPC vote denial logic."""
        raft = Raft("test-node")
        
        # First vote
        raft.handle_request_vote("candidate1", 1, 0, 0)
        assert raft.voted_for == "candidate1"
        
        # Second vote in same term should be denied
        response = raft.handle_request_vote("candidate2", 1, 0, 0)
        
        assert response["vote_granted"] is False
        assert raft.voted_for == "candidate1"  # Should not change
    
    def test_term_update(self):
        """Test that higher term updates current term."""
        raft = Raft("test-node")
        raft.current_term = 5
        
        # Candidate with higher term should update our term
        response = raft.handle_request_vote("candidate", 7, 0, 0)
        
        assert response["term"] == 7
        assert raft.current_term == 7
        assert raft.state == RaftState.FOLLOWER
        assert raft.voted_for == "candidate"
    
    def test_append_entries_term_update(self):
        """Test AppendEntries RPC term update."""
        raft = Raft("test-node")
        raft.current_term = 3
        
        # Leader with higher term should update our term
        response = raft.handle_append_entries("leader", 5, 0, 0, [], 0)
        
        assert response["term"] == 5
        assert raft.current_term == 5
        assert raft.state == RaftState.FOLLOWER
    
    def test_election_timeout(self):
        """Test election timeout triggers state transition."""
        raft = Raft("test-node")
        raft.election_timeout = 0.01  # Very short timeout for testing
        
        # Should start as follower
        assert raft.state == RaftState.FOLLOWER
        
        # Wait for election timeout
        time.sleep(0.02)
        raft.tick()
        
        # Should now be candidate
        assert raft.state == RaftState.CANDIDATE
        assert raft.current_term == 1
        assert raft.voted_for == "test-node"
    
    def test_state_info(self):
        """Test get_state_info returns correct information."""
        raft = Raft("test-node")
        raft.current_term = 3
        raft.voted_for = "other-node"
        
        info = raft.get_state_info()
        
        assert info["node_id"] == "test-node"
        assert info["state"] == "follower"
        assert info["current_term"] == 3
        assert info["voted_for"] == "other-node"
        assert info["commit_index"] == 0
        assert info["last_applied"] == 0
        assert info["log_length"] == 0
        assert "election_timeout" in info
        assert "time_since_last_heartbeat" in info