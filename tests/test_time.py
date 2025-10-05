"""Tests for time synchronization functionality."""

import pytest
import time
import threading
import socket
from src.time.lamport import LamportClock, VectorClock, MessageOrdering
from src.time.sync import TimeSyncClient, TimeSyncServer, BoundedReordering, TimeSyncConfig


class TestLamportClock:
    """Test Lamport clock implementation."""
    
    def test_initial_clock(self):
        """Test initial clock state."""
        clock = LamportClock()
        assert clock.get_time() == 0
    
    def test_tick(self):
        """Test clock ticking."""
        clock = LamportClock()
        assert clock.tick() == 1
        assert clock.tick() == 2
        assert clock.get_time() == 2
    
    def test_update(self):
        """Test clock update from received message."""
        clock = LamportClock()
        clock.tick()  # clock = 1
        clock.tick()  # clock = 2
        
        # Update with higher time
        new_time = clock.update(5)
        assert new_time == 6
        assert clock.get_time() == 6
        
        # Update with lower time (should still increment)
        new_time = clock.update(3)
        assert new_time == 7
        assert clock.get_time() == 7
    
    def test_compare(self):
        """Test clock comparison."""
        clock = LamportClock()
        clock.tick()  # clock = 1
        
        assert clock.compare(0) == "after"
        assert clock.compare(1) == "equal"
        assert clock.compare(2) == "before"
    
    def test_concurrent_access(self):
        """Test thread safety."""
        clock = LamportClock()
        results = []
        
        def tick_worker():
            for _ in range(10):
                results.append(clock.tick())
                time.sleep(0.001)
        
        threads = [threading.Thread(target=tick_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All results should be unique and sequential
        assert len(set(results)) == len(results)
        assert max(results) == 30


class TestVectorClock:
    """Test vector clock implementation."""
    
    def test_initial_clock(self):
        """Test initial vector clock state."""
        clock = VectorClock("node1", 3)
        assert clock.get_time() == [0, 0, 0]
    
    def test_tick(self):
        """Test vector clock ticking."""
        clock = VectorClock("node1", 3)
        vector = clock.tick()
        assert vector[0] == 1  # node1's index is 0
        assert vector[1] == 0
        assert vector[2] == 0
    
    def test_update(self):
        """Test vector clock update."""
        clock = VectorClock("node1", 3)
        clock.tick()  # [1, 0, 0]
        
        # Update with received vector
        received_vector = [2, 1, 0]
        new_vector = clock.update(received_vector)
        assert new_vector == [2, 1, 1]  # Max of each + increment own
    
    def test_compare(self):
        """Test vector clock comparison."""
        clock = VectorClock("node1", 3)
        
        # Equal vectors
        assert clock.compare([0, 0, 0]) == "equal"
        
        # Before relationship
        clock.update([1, 0, 0])
        assert clock.compare([0, 0, 0]) == "after"
        assert clock.compare([2, 1, 0]) == "before"
        
        # Concurrent relationship
        assert clock.compare([0, 1, 0]) == "concurrent"


class TestMessageOrdering:
    """Test message ordering system."""
    
    def test_logical_clock_ordering(self):
        """Test message ordering with logical clocks."""
        ordering = MessageOrdering("node1", use_vector_clocks=False)
        
        # Create timestamp
        timestamp = ordering.create_timestamp()
        assert timestamp["clock_type"] == "logical"
        assert "logical_time" in timestamp
        assert timestamp["logical_time"] == 1
        
        # Update from received message
        received_timestamp = {
            "clock_type": "logical",
            "logical_time": 5
        }
        new_timestamp = ordering.update_from_message(received_timestamp)
        assert new_timestamp["logical_time"] == 6
    
    def test_vector_clock_ordering(self):
        """Test message ordering with vector clocks."""
        ordering = MessageOrdering("node1", use_vector_clocks=True, total_nodes=3)
        
        # Create timestamp
        timestamp = ordering.create_timestamp()
        assert timestamp["clock_type"] == "vector"
        assert "vector_time" in timestamp
        assert timestamp["vector_time"] == [1, 0, 0]
        
        # Update from received message
        received_timestamp = {
            "clock_type": "vector",
            "vector_time": [2, 1, 0]
        }
        new_timestamp = ordering.update_from_message(received_timestamp)
        assert new_timestamp["vector_time"] == [2, 1, 1]


class TestTimeSyncClient:
    """Test time synchronization client."""
    
    def test_initial_state(self):
        """Test initial client state."""
        client = TimeSyncClient("test-node")
        assert client.node_id == "test-node"
        assert len(client.offsets) == 0
        assert not client.running
    
    def test_average_offset_empty(self):
        """Test average offset with no peers."""
        client = TimeSyncClient("test-node")
        assert client.get_average_offset() == 0.0
    
    def test_average_offset_with_peers(self):
        """Test average offset calculation."""
        client = TimeSyncClient("test-node")
        client.offsets = {"peer1": 0.1, "peer2": 0.2, "peer3": 0.3}
        assert abs(client.get_average_offset() - 0.2) < 0.001
    
    def test_synchronized_time(self):
        """Test synchronized time calculation."""
        client = TimeSyncClient("test-node")
        client.offsets = {"peer1": 0.1}
        
        sync_time = client.get_synchronized_time()
        current_time = time.time()
        
        # Should be approximately current time + offset
        assert abs(sync_time - (current_time + 0.1)) < 0.1


class TestBoundedReordering:
    """Test bounded reordering system."""
    
    def test_initial_state(self):
        """Test initial reordering state."""
        reordering = BoundedReordering()
        assert reordering.get_pending_count() == 0
    
    def test_message_ordering(self):
        """Test message ordering with bounded delay."""
        reordering = BoundedReordering(max_delay_ms=50)
        
        # Add messages with different timestamps
        msg1 = {"id": "1", "timestamp": time.time() - 0.1}  # 100ms ago
        msg2 = {"id": "2", "timestamp": time.time() - 0.05}  # 50ms ago
        msg3 = {"id": "3", "timestamp": time.time()}  # now
        
        # First message should be ready immediately (100ms > 50ms)
        ready = reordering.add_message(msg1)
        assert len(ready) == 1
        assert ready[0]["id"] == "1"
        
        # Second message should not be ready yet (50ms = 50ms)
        ready = reordering.add_message(msg2)
        assert len(ready) == 0
        
        # Wait a bit and add third message
        time.sleep(0.06)  # Wait 60ms
        ready = reordering.add_message(msg3)
        assert len(ready) == 1  # msg2 should now be ready
        assert ready[0]["id"] == "2"
    
    def test_pending_count(self):
        """Test pending message count."""
        reordering = BoundedReordering(max_delay_ms=100)
        
        msg = {"id": "1", "timestamp": time.time()}
        reordering.add_message(msg)
        assert reordering.get_pending_count() == 1


@pytest.mark.integration
class TestTimeSyncIntegration:
    """Integration tests for time synchronization."""
    
    def test_client_server_sync(self):
        """Test time sync between client and server."""
        # Start server
        server = TimeSyncServer("test-server", port=9101)
        server.start()
        time.sleep(0.1)  # Give server time to start
        
        try:
            # Create client and measure offset
            client = TimeSyncClient("test-client")
            offset = client.measure_offset("127.0.0.1", 9101, "test-server")
            
            # Should get a valid offset (might be small due to localhost)
            assert offset is not None
            assert isinstance(offset, float)
            
        finally:
            server.stop()
    
    def test_multiple_nodes_sync(self):
        """Test synchronization between multiple nodes."""
        # Start two servers
        server1 = TimeSyncServer("server1", port=9102)
        server2 = TimeSyncServer("server2", port=9103)
        
        server1.start()
        server2.start()
        time.sleep(0.1)
        
        try:
            # Create client and sync with both servers
            client = TimeSyncClient("client")
            
            offset1 = client.measure_offset("127.0.0.1", 9102, "server1")
            offset2 = client.measure_offset("127.0.0.1", 9103, "server2")
            
            # Both should return valid offsets
            assert offset1 is not None
            assert offset2 is not None
            
            # Average offset should be calculated
            avg_offset = client.get_average_offset()
            assert isinstance(avg_offset, float)
            
        finally:
            server1.stop()
            server2.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

