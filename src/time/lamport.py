import threading
import time
from typing import Dict, List, Optional


class LamportClock:
    """Thread-safe Lamport clock implementation"""
    
    def __init__(self, initial: int = 0):
        self.t = initial
        self.lock = threading.Lock()
    
    def tick(self) -> int:
        """Increment clock and return new value."""
        with self.lock:
            self.t += 1
            return self.t
    
    def update(self, received: int) -> int:
        """Update clock based on received message time."""
        with self.lock:
            self.t = max(self.t, received) + 1
            return self.t
    
    def get_time(self) -> int:
        """Get current logical time."""
        with self.lock:
            return self.t
    
    def compare(self, other_time: int) -> str:
        """Compare with another logical time."""
        with self.lock:
            if self.t < other_time:
                return "before"
            elif self.t > other_time:
                return "after"
            else:
                return "equal"


class VectorClock:
    """Vector clock for complete causal ordering."""
    
    def __init__(self, node_id: str, total_nodes: int):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.clock = [0] * total_nodes
        self.node_index = hash(node_id) % total_nodes
        self.lock = threading.Lock()
    
    def tick(self) -> List[int]:
        """Increment own clock and return current vector."""
        with self.lock:
            self.clock[self.node_index] += 1
            return self.clock.copy()
    
    def update(self, received_vector: List[int]) -> List[int]:
        """Update vector clock based on received message."""
        with self.lock:
            for i in range(self.total_nodes):
                self.clock[i] = max(self.clock[i], received_vector[i])
            self.clock[self.node_index] += 1
            return self.clock.copy()
    
    def get_time(self) -> List[int]:
        """Get current vector time."""
        with self.lock:
            return self.clock.copy()
    
    def compare(self, other_vector: List[int]) -> str:
        """Compare two vector clocks: 'before', 'after', 'concurrent', or 'equal'."""
        if len(self.clock) != len(other_vector):
            return "incompatible"
        
        less = any(self.clock[i] < other_vector[i] for i in range(len(self.clock)))
        greater = any(self.clock[i] > other_vector[i] for i in range(len(self.clock)))
        
        if less and not greater:
            return "before"
        elif greater and not less:
            return "after"
        elif not less and not greater:
            return "equal"
        else:
            return "concurrent"


class MessageOrdering:
    """Message ordering system with time synchronization support."""
    
    def __init__(self, node_id: str, use_vector_clocks: bool = False, total_nodes: int = 3):
        self.node_id = node_id
        self.use_vector_clocks = use_vector_clocks
        
        if use_vector_clocks:
            self.vector_clock = VectorClock(node_id, total_nodes)
            self.lamport_clock = None
        else:
            self.lamport_clock = LamportClock()
            self.vector_clock = None
    
    def create_timestamp(self) -> Dict:
        """Create a timestamp for outgoing messages."""
        timestamp = {
            "node_id": self.node_id,
            "physical_time": time.time(),
            "timestamp": time.time()
        }
        
        if self.use_vector_clocks and self.vector_clock:
            timestamp["vector_time"] = self.vector_clock.tick()
            timestamp["clock_type"] = "vector"
        elif self.lamport_clock:
            timestamp["logical_time"] = self.lamport_clock.tick()
            timestamp["clock_type"] = "logical"
        
        return timestamp
    
    def update_from_message(self, message_timestamp: Dict) -> Dict:
        """Update clocks based on received message timestamp."""
        if message_timestamp.get("clock_type") == "logical" and self.lamport_clock:
            received_time = message_timestamp.get("logical_time", 0)
            self.lamport_clock.update(received_time)
        
        elif message_timestamp.get("clock_type") == "vector" and self.vector_clock:
            received_vector = message_timestamp.get("vector_time", [])
            self.vector_clock.update(received_vector)
        
        return self.create_timestamp()
    
    def get_current_time(self) -> Dict:
        """Get current time information."""
        current_time = {
            "node_id": self.node_id,
            "physical_time": time.time(),
            "timestamp": time.time()
        }
        
        if self.use_vector_clocks and self.vector_clock:
            current_time["vector_time"] = self.vector_clock.get_time()
            current_time["clock_type"] = "vector"
        elif self.lamport_clock:
            current_time["logical_time"] = self.lamport_clock.get_time()
            current_time["clock_type"] = "logical"
        
        return current_time
