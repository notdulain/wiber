"""
Time Synchronization Module for Distributed Systems

This module provides various time synchronization mechanisms:
1. NTP-based synchronization
2. Logical clocks (Lamport timestamps)
3. Vector clocks
4. Clock skew detection and correction
"""

import time
import threading
import socket
import struct
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ClockType(Enum):
    PHYSICAL = "physical"
    LOGICAL = "logical"
    VECTOR = "vector"


@dataclass
class TimeSyncConfig:
    """Configuration for time synchronization"""
    ntp_servers: List[str] = None
    sync_interval: float = 60.0  # seconds
    max_skew_threshold: float = 100.0  # milliseconds
    drift_correction: bool = True
    logical_clock_enabled: bool = True
    vector_clock_enabled: bool = False


class NTPClient:
    """NTP client for time synchronization"""
    
    NTP_PACKET_FORMAT = "!12I"
    NTP_DELTA = 2208988800  # 1970-01-01 00:00:00
    NTP_QUERY_DELAY = 0.1
    
    def __init__(self, servers: List[str] = None):
        self.servers = servers or [
            "pool.ntp.org",
            "time.google.com",
            "time.cloudflare.com"
        ]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(5)
    
    def get_ntp_time(self, server: str) -> Optional[Tuple[float, float]]:
        """Get time from NTP server, returns (server_time, round_trip_delay)"""
        try:
            # Create NTP packet
            packet = bytearray(48)
            packet[0] = 0x1b  # LI, VN, Mode
            
            # Send packet
            self.socket.sendto(packet, (server, 123))
            
            # Receive response
            data, _ = self.socket.recvfrom(48)
            
            # Parse response
            unpacked = struct.unpack(self.NTP_PACKET_FORMAT, data)
            t1 = time.time()  # Time when response was received
            
            # Extract timestamps
            t0 = (unpacked[10] - self.NTP_DELTA) + (unpacked[11] / 2**32)
            t2 = (unpacked[8] - self.NTP_DELTA) + (unpacked[9] / 2**32)
            t3 = (unpacked[6] - self.NTP_DELTA) + (unpacked[7] / 2**32)
            
            # Calculate round trip delay and offset
            delay = (t1 - t0) - (t2 - t3)
            offset = ((t2 - t0) + (t3 - t1)) / 2
            
            return t2, delay
            
        except Exception as e:
            print(f"NTP query failed for {server}: {e}")
            return None
    
    def get_best_time(self) -> Optional[float]:
        """Get the best time estimate from multiple NTP servers"""
        results = []
        
        for server in self.servers:
            result = self.get_ntp_time(server)
            if result:
                server_time, delay = result
                results.append((server_time, delay))
        
        if not results:
            return None
        
        # Use the result with minimum delay
        best_time, _ = min(results, key=lambda x: x[1])
        return best_time


class LogicalClock:
    """Lamport logical clock implementation"""
    
    def __init__(self):
        self.clock = 0
        self.lock = threading.Lock()
    
    def tick(self) -> int:
        """Increment clock and return new value"""
        with self.lock:
            self.clock += 1
            return self.clock
    
    def update(self, received_time: int) -> int:
        """Update clock based on received message time"""
        with self.lock:
            self.clock = max(self.clock, received_time) + 1
            return self.clock
    
    def get_time(self) -> int:
        """Get current logical time"""
        with self.lock:
            return self.clock


class VectorClock:
    """Vector clock implementation for causal ordering"""
    
    def __init__(self, node_id: str, total_nodes: int):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.clock = [0] * total_nodes
        self.node_index = hash(node_id) % total_nodes
        self.lock = threading.Lock()
    
    def tick(self) -> List[int]:
        """Increment own clock and return current vector"""
        with self.lock:
            self.clock[self.node_index] += 1
            return self.clock.copy()
    
    def update(self, received_vector: List[int]) -> List[int]:
        """Update vector clock based on received message"""
        with self.lock:
            for i in range(self.total_nodes):
                self.clock[i] = max(self.clock[i], received_vector[i])
            self.clock[self.node_index] += 1
            return self.clock.copy()
    
    def get_time(self) -> List[int]:
        """Get current vector time"""
        with self.lock:
            return self.clock.copy()
    
    def compare(self, other_vector: List[int]) -> str:
        """Compare two vector clocks: 'before', 'after', 'concurrent', or 'equal'"""
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


class TimeSynchronizer:
    """Main time synchronization coordinator"""
    
    def __init__(self, config: TimeSyncConfig, node_id: str = "default"):
        self.config = config
        self.node_id = node_id
        self.physical_clock_offset = 0.0
        self.last_sync_time = 0.0
        self.ntp_client = NTPClient(config.ntp_servers) if config.ntp_servers else None
        self.logical_clock = LogicalClock() if config.logical_clock_enabled else None
        self.vector_clock = None  # Will be initialized if needed
        self.lock = threading.Lock()
        self.sync_thread = None
        self.running = False
    
    def start_sync(self):
        """Start background synchronization thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            return
        
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
    
    def stop_sync(self):
        """Stop background synchronization"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join()
    
    def _sync_loop(self):
        """Background synchronization loop"""
        while self.running:
            try:
                self.sync_with_ntp()
                time.sleep(self.config.sync_interval)
            except Exception as e:
                print(f"Sync error: {e}")
                time.sleep(5)
    
    def sync_with_ntp(self) -> bool:
        """Synchronize with NTP servers"""
        if not self.ntp_client:
            return False
        
        ntp_time = self.ntp_client.get_best_time()
        if ntp_time is None:
            return False
        
        current_time = time.time()
        offset = ntp_time - current_time
        
        with self.lock:
            self.physical_clock_offset = offset
            self.last_sync_time = current_time
        
        print(f"Time sync: offset={offset:.3f}s, ntp_time={ntp_time:.3f}")
        return True
    
    def get_physical_time(self) -> float:
        """Get synchronized physical time"""
        with self.lock:
            return time.time() + self.physical_clock_offset
    
    def get_logical_time(self) -> int:
        """Get logical time"""
        if self.logical_clock:
            return self.logical_clock.get_time()
        return 0
    
    def get_vector_time(self) -> List[int]:
        """Get vector time"""
        if self.vector_clock:
            return self.vector_clock.get_time()
        return []
    
    def create_timestamp(self, clock_type: ClockType = ClockType.PHYSICAL) -> Dict:
        """Create a timestamp with specified clock type"""
        timestamp = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "clock_type": clock_type.value
        }
        
        if clock_type == ClockType.PHYSICAL:
            timestamp["physical_time"] = self.get_physical_time()
        elif clock_type == ClockType.LOGICAL and self.logical_clock:
            timestamp["logical_time"] = self.logical_clock.tick()
        elif clock_type == ClockType.VECTOR and self.vector_clock:
            timestamp["vector_time"] = self.vector_clock.tick()
        
        return timestamp
    
    def update_from_message(self, message_timestamp: Dict) -> Dict:
        """Update clocks based on received message timestamp"""
        if message_timestamp.get("clock_type") == "logical" and self.logical_clock:
            received_time = message_timestamp.get("logical_time", 0)
            self.logical_clock.update(received_time)
        
        elif message_timestamp.get("clock_type") == "vector" and self.vector_clock:
            received_vector = message_timestamp.get("vector_time", [])
            self.vector_clock.update(received_vector)
        
        return self.create_timestamp(ClockType(message_timestamp.get("clock_type", "physical")))
    
    def detect_clock_skew(self, other_timestamp: Dict) -> float:
        """Detect clock skew between this node and another"""
        if "physical_time" not in other_timestamp:
            return 0.0
        
        our_time = self.get_physical_time()
        their_time = other_timestamp["physical_time"]
        
        return abs(our_time - their_time) * 1000  # Return in milliseconds


# Global time synchronizer instance
_time_sync = None

def get_time_sync(config: TimeSyncConfig = None, node_id: str = "default") -> TimeSynchronizer:
    """Get or create global time synchronizer instance"""
    global _time_sync
    if _time_sync is None:
        _time_sync = TimeSynchronizer(config or TimeSyncConfig(), node_id)
    return _time_sync


def simulate_clock_skew(base_skew_ms: float = 0, drift_ms_per_sec: float = 0, 
                       random_variation_ms: int = 0) -> float:
    """Simulate realistic clock skew for testing"""
    current_time = time.time()
    
    # Base skew
    skew = base_skew_ms
    
    # Drift over time
    if drift_ms_per_sec != 0:
        skew += drift_ms_per_sec * current_time
    
    # Random variation
    if random_variation_ms > 0:
        skew += random.uniform(-random_variation_ms, random_variation_ms)
    
    return skew
