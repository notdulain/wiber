import time
from typing import Dict, List


class FailureDetector:
    def __init__(self, peers: List[str], heartbeat_timeout: float = 3.0):
        self.peers = peers
        self.heartbeat_timeout = heartbeat_timeout
        self.peer_status = {p: {"last_ok": 0.0, "alive": False} for p in peers}

    def mark_alive(self, peer: str, timestamp: float):
        """Mark a peer as alive with current timestamp"""
        self.peer_status[peer] = {"last_ok": timestamp, "alive": True}

    def check_failures(self, current_time: float) -> List[str]:
        """Return list of failed peers based on current time"""
        failed = []
        for peer, status in self.peer_status.items():
            if current_time - status["last_ok"] > self.heartbeat_timeout:
                status["alive"] = False
                failed.append(peer)
        return failed

    def get_alive_peers(self) -> List[str]:
        """Return list of currently alive peers"""
        return [p for p, status in self.peer_status.items() if status["alive"]]

    def is_alive(self, peer: str) -> bool:
        """Check if a specific peer is alive"""
        return self.peer_status.get(peer, {}).get("alive", False)
