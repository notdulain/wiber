"""
Tests for time synchronization functionality
"""

import pytest
import time
import threading
from src.utils.time_sync import (
    TimeSyncConfig, TimeSynchronizer, LogicalClock, VectorClock,
    ClockType, simulate_clock_skew, NTPClient
)


class TestLogicalClock:
    """Test logical clock implementation"""
    
    def test_initial_clock(self):
        """Test initial clock state"""
        clock = LogicalClock()
        assert clock.get_time() == 0
    
    def test_tick(self):
        """Test clock ticking"""
        clock = LogicalClock()
        assert clock.tick() == 1
        assert clock.tick() == 2
        assert clock.get_time() == 2
    
    def test_update(self):
        """Test clock update from received message"""
        clock = LogicalClock()
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
    
    def test_concurrent_access(self):
        """Test thread safety"""
        clock = LogicalClock()
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
    """Test vector clock implementation"""
    
    def test_initial_clock(self):
        """Test initial vector clock state"""
        clock = VectorClock("node1", 3)
        assert clock.get_time() == [0, 0, 0]
    
    def test_tick(self):
        """Test vector clock ticking"""
        clock = VectorClock("node1", 3)
        vector = clock.tick()
        assert vector[0] == 1  # node1's index is 0
        assert vector[1] == 0
        assert vector[2] == 0
    
    def test_update(self):
        """Test vector clock update"""
        clock = VectorClock("node1", 3)
        clock.tick()  # [1, 0, 0]
        
        # Update with received vector
        received_vector = [2, 1, 0]
        new_vector = clock.update(received_vector)
        assert new_vector == [2, 1, 1]  # Max of each + increment own
    
    def test_compare(self):
        """Test vector clock comparison"""
        clock = VectorClock("node1", 3)
        
        # Equal vectors
        assert clock.compare([0, 0, 0]) == "equal"
        
        # Before relationship
        clock.update([1, 0, 0])
        assert clock.compare([0, 0, 0]) == "after"
        assert clock.compare([2, 1, 0]) == "before"
        
        # Concurrent relationship
        assert clock.compare([0, 1, 0]) == "concurrent"


class TestTimeSynchronizer:
    """Test time synchronizer"""
    
    def test_initial_state(self):
        """Test initial synchronizer state"""
        config = TimeSyncConfig()
        sync = TimeSynchronizer(config, "test-node")
        
        assert sync.node_id == "test-node"
        assert sync.physical_clock_offset == 0.0
    
    def test_create_timestamp_physical(self):
        """Test physical timestamp creation"""
        config = TimeSyncConfig()
        sync = TimeSynchronizer(config, "test-node")
        
        timestamp = sync.create_timestamp(ClockType.PHYSICAL)
        
        assert timestamp["node_id"] == "test-node"
        assert timestamp["clock_type"] == "physical"
        assert "physical_time" in timestamp
        assert "timestamp" in timestamp
    
    def test_create_timestamp_logical(self):
        """Test logical timestamp creation"""
        config = TimeSyncConfig(logical_clock_enabled=True)
        sync = TimeSynchronizer(config, "test-node")
        
        timestamp = sync.create_timestamp(ClockType.LOGICAL)
        
        assert timestamp["clock_type"] == "logical"
        assert "logical_time" in timestamp
        assert timestamp["logical_time"] == 1  # First tick
    
    def test_create_timestamp_vector(self):
        """Test vector timestamp creation"""
        config = TimeSyncConfig(vector_clock_enabled=True)
        sync = TimeSynchronizer(config, "test-node")
        sync.vector_clock = VectorClock("test-node", 3)
        
        timestamp = sync.create_timestamp(ClockType.VECTOR)
        
        assert timestamp["clock_type"] == "vector"
        assert "vector_time" in timestamp
        assert timestamp["vector_time"] == [1, 0, 0]  # First tick for node 0
    
    def test_update_from_message_logical(self):
        """Test updating logical clock from message"""
        config = TimeSyncConfig(logical_clock_enabled=True)
        sync = TimeSynchronizer(config, "test-node")
        
        # Create initial timestamp
        timestamp1 = sync.create_timestamp(ClockType.LOGICAL)
        assert timestamp1["logical_time"] == 1
        
        # Simulate receiving message with higher logical time
        received_timestamp = {
            "node_id": "other-node",
            "clock_type": "logical",
            "logical_time": 5
        }
        
        timestamp2 = sync.update_from_message(received_timestamp)
        assert timestamp2["logical_time"] == 6  # Max(1, 5) + 1


class TestClockSkewSimulation:
    """Test clock skew simulation"""
    
    def test_no_skew(self):
        """Test simulation with no skew"""
        skew = simulate_clock_skew(0, 0, 0)
        assert skew == 0
    
    def test_base_skew(self):
        """Test base skew simulation"""
        skew = simulate_clock_skew(100, 0, 0)
        assert skew == 100
    
    def test_drift_simulation(self):
        """Test clock drift simulation"""
        # Small drift should be close to 0 initially
        skew1 = simulate_clock_skew(0, 0.001, 0)  # 0.001 ms per second
        time.sleep(0.1)  # Wait 100ms
        skew2 = simulate_clock_skew(0, 0.001, 0)
        
        # Should be slightly different due to drift
        assert abs(skew2 - skew1) > 0
    
    def test_random_variation(self):
        """Test random variation in skew"""
        skews = [simulate_clock_skew(0, 0, 10) for _ in range(10)]
        
        # Should have some variation
        assert len(set(skews)) > 1
        assert all(-10 <= s <= 10 for s in skews)


class TestMessageOrdering:
    """Test message ordering scenarios"""
    
    def test_physical_vs_logical_ordering(self):
        """Test ordering differences between physical and logical clocks"""
        config = TimeSyncConfig(logical_clock_enabled=True)
        sync = TimeSynchronizer(config, "test-node")
        
        # Create messages with different clock types
        physical_msg = sync.create_timestamp(ClockType.PHYSICAL)
        logical_msg = sync.create_timestamp(ClockType.LOGICAL)
        
        # Both should have timestamps
        assert "physical_time" in physical_msg
        assert "logical_time" in logical_msg
        
        # Physical time should be actual time
        assert physical_msg["physical_time"] > 0
        
        # Logical time should be sequential
        assert logical_msg["logical_time"] == 1
    
    def test_skew_impact_on_ordering(self):
        """Test how clock skew affects message ordering"""
        # Simulate two nodes with different skews
        skew1 = simulate_clock_skew(100, 0, 0)  # +100ms
        skew2 = simulate_clock_skew(-50, 0, 0)  # -50ms
        
        # Node 1 sends message first (but with +100ms skew)
        time1 = time.time() + (skew1 / 1000.0)
        
        time.sleep(0.1)  # Wait 100ms
        
        # Node 2 sends message later (but with -50ms skew)
        time2 = time.time() + (skew2 / 1000.0)
        
        # Due to skew, time2 might appear earlier than time1
        # This demonstrates the ordering problem
        assert abs(time1 - time2) < 0.2  # Should be close due to skew


@pytest.mark.integration
class TestTimeSyncIntegration:
    """Integration tests for time synchronization"""
    
    def test_producer_consumer_time_sync(self):
        """Test time sync between producer and consumer"""
        config = TimeSyncConfig(logical_clock_enabled=True)
        
        # Create producer and consumer synchronizers
        producer_sync = TimeSynchronizer(config, "producer")
        consumer_sync = TimeSynchronizer(config, "consumer")
        
        # Producer creates message
        producer_timestamp = producer_sync.create_timestamp(ClockType.LOGICAL)
        
        # Consumer receives and updates
        consumer_timestamp = consumer_sync.update_from_message(producer_timestamp)
        
        # Consumer's logical time should be higher
        assert consumer_timestamp["logical_time"] > producer_timestamp["logical_time"]
    
    def test_multiple_nodes_synchronization(self):
        """Test synchronization between multiple nodes"""
        config = TimeSyncConfig(logical_clock_enabled=True)
        
        nodes = [
            TimeSynchronizer(config, f"node-{i}") 
            for i in range(3)
        ]
        
        # Each node creates a message
        timestamps = [
            node.create_timestamp(ClockType.LOGICAL)
            for node in nodes
        ]
        
        # All should have logical times
        for ts in timestamps:
            assert "logical_time" in ts
            assert ts["logical_time"] == 1
        
        # Simulate message passing between nodes
        for i in range(len(nodes)):
            for j in range(len(nodes)):
                if i != j:
                    # Node j receives message from node i
                    nodes[j].update_from_message(timestamps[i])
        
        # All nodes should have updated their clocks
        for node in nodes:
            current_time = node.get_logical_time()
            assert current_time > 1  # Should have been updated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
