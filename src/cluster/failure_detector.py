"""Simple failure detector utility.

Tracks last successful interaction timestamp per peer and marks peers as
alive/dead based on a heartbeat timeout. This is for observability/backoff
and should not replace Raft's own election timers.
"""

from __future__ import annotations

import time
from typing import Dict, List


class FailureDetector:
    def __init__(self, peers: List[str], heartbeat_timeout: float = 0.3):
        self.peers = peers
        self.heartbeat_timeout = heartbeat_timeout
        self.peer_status = {p: {"last_ok": 0.0, "alive": False} for p in peers}

    def mark_alive(self, peer: str, timestamp: float | None = None) -> None:
        """Mark a peer as alive with current timestamp."""
        ts = timestamp if timestamp is not None else time.time()
        self.peer_status[peer] = {"last_ok": ts, "alive": True}

    def check_failures(self, current_time: float | None = None) -> List[str]:
        """Return list of failed peers based on current time."""
        now = current_time if current_time is not None else time.time()
        failed = []
        for peer, status in self.peer_status.items():
            if now - status["last_ok"] > self.heartbeat_timeout:
                status["alive"] = False
                failed.append(peer)
        return failed

    def get_alive_peers(self) -> List[str]:
        """Return list of currently alive peers."""
        return [p for p, status in self.peer_status.items() if status["alive"]]

    def is_alive(self, peer: str) -> bool:
        """Check if a specific peer is alive."""
        return self.peer_status.get(peer, {}).get("alive", False)

