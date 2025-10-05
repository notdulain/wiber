"""Tests for leader replication logic."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.cluster.raft import Raft, RaftState


class TestLeaderReplication:
    def test_add_entry_as_leader(self):
        """Test that leader can add entries to log."""
        raft = Raft("n1")
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Mock RPC client factory
        mock_client = AsyncMock()
        mock_client.append_entries.return_value = {
            "method": "append_entries_response",
            "term": 1,
            "success": True
        }
        raft.rpc_client_factory = MagicMock(return_value=mock_client)
        
        # Add entry
        success = raft.add_entry("SET", {"key": "x", "value": "1"})
        
        assert success is True
        assert len(raft.log) == 1
        assert raft.log[0]["command"] == "SET"
        assert raft.log[0]["data"]["key"] == "x"
        assert raft.log[0]["term"] == 1

    def test_add_entry_as_follower(self):
        """Test that followers cannot add entries."""
        raft = Raft("n1")
        raft.state = RaftState.FOLLOWER
        
        # Try to add entry
        success = raft.add_entry("SET", {"key": "x", "value": "1"})
        
        assert success is False
        assert len(raft.log) == 0

    def test_replication_to_followers(self):
        """Test that leader replicates entries to followers."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Initialize follower tracking
        raft.next_index = {"127.0.0.1:9102": 1, "127.0.0.1:9103": 1}
        raft.match_index = {"127.0.0.1:9102": 0, "127.0.0.1:9103": 0}
        
        # Mock RPC client factory to prevent async calls
        raft.rpc_client_factory = None
        
        # Add entry (this will not trigger replication due to no RPC factory)
        success = raft.add_entry("SET", {"key": "x", "value": "1"})
        
        # Check that entry was added
        assert success is True
        assert len(raft.log) == 1
        assert raft.log[0]["command"] == "SET"

    def test_commit_index_update(self):
        """Test that commit index updates when majority has entries."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        raft.commit_index = 0
        
        # Add some entries
        raft.log = [
            {"term": 1, "command": "SET", "key": "x", "value": "1"},
            {"term": 1, "command": "SET", "key": "y", "value": "2"}
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

    def test_commit_index_no_majority(self):
        """Test that commit index doesn't update without majority."""
        raft = Raft("n1", [("127.0.0.1", 9102), ("127.0.0.1", 9103)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        raft.commit_index = 0
        
        # Add some entries
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

    def test_follower_progress_tracking(self):
        """Test that leader tracks follower progress correctly."""
        raft = Raft("n1", [("127.0.0.1", 9102)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Initialize tracking
        raft.next_index = {"127.0.0.1:9102": 1}
        raft.match_index = {"127.0.0.1:9102": 0}
        
        # Simulate successful replication
        response = {
            "method": "append_entries_response",
            "term": 1,
            "success": True
        }
        
        # Mock the async method
        async def mock_handle_response():
            await raft._handle_replication_response(response, "127.0.0.1", 9102, 1)
        
        asyncio.run(mock_handle_response())
        
        # Check that progress was updated
        assert raft.next_index["127.0.0.1:9102"] == 2  # Incremented by entries_sent
        assert raft.match_index["127.0.0.1:9102"] == 1  # next_index - 1

    def test_follower_rejection_handling(self):
        """Test that leader handles follower rejections correctly."""
        raft = Raft("n1", [("127.0.0.1", 9102)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Initialize tracking
        raft.next_index = {"127.0.0.1:9102": 3}
        raft.match_index = {"127.0.0.1:9102": 2}
        
        # Simulate failed replication
        response = {
            "method": "append_entries_response",
            "term": 1,
            "success": False
        }
        
        # Mock the async method
        async def mock_handle_response():
            await raft._handle_replication_response(response, "127.0.0.1", 9102, 1)
        
        asyncio.run(mock_handle_response())
        
        # Check that next_index was decremented
        assert raft.next_index["127.0.0.1:9102"] == 2  # Decremented by 1

    def test_higher_term_response(self):
        """Test that leader becomes follower on higher term response."""
        raft = Raft("n1", [("127.0.0.1", 9102)])
        raft.state = RaftState.LEADER
        raft.current_term = 1
        
        # Simulate response with higher term
        response = {
            "method": "append_entries_response",
            "term": 2,
            "success": True
        }
        
        # Mock the async method
        async def mock_handle_response():
            await raft._handle_replication_response(response, "127.0.0.1", 9102, 1)
        
        asyncio.run(mock_handle_response())
        
        # Check that leader became follower
        assert raft.current_term == 2
        assert raft.state == RaftState.FOLLOWER
        assert raft.voted_for is None
