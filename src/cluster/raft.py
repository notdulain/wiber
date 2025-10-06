"""Raft consensus algorithm implementation.

Implements the Raft consensus algorithm for distributed systems.
Handles leader election, log replication, and state management.

Based on the Raft paper: "In Search of an Understandable Consensus Algorithm"
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class RaftState(Enum):
    """Raft node states."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate" 
    LEADER = "leader"


@dataclass(frozen=True)
class LogEntry:
    index: int
    term: int
    payload: Dict[str, Any]


class Raft:
    """Raft consensus algorithm implementation."""
    
    def __init__(self, node_id: str, other_nodes: list = None):
        self.node_id = node_id
        self.other_nodes = other_nodes or []  # List of (host, port) tuples
        # Map peer key ("host:port") to address for convenience
        self._peers: Dict[str, tuple[str, int]] = {f"{h}:{p}": (h, p) for (h, p) in self.other_nodes}
        
        # Persistent state (survives crashes)
        self.current_term: int = 0
        self.voted_for: Optional[str] = None  # None, or node_id of candidate voted for
        # Raft log (Phase 3): list of LogEntry. Indexing is 1-based.
        self.log: List[LogEntry] = []
        
        # Volatile state (reset on restart)
        self.commit_index: int = 0  # Highest log entry known to be committed
        self.last_applied: int = 0  # Highest log entry applied to state machine
        
        # Leader state (only valid when state == LEADER)
        self.next_index: Dict[str, int] = {}  # For each server, index of next log entry to send
        self.match_index: Dict[str, int] = {}  # For each server, index of highest log entry known to be replicated
        
        # Current state
        self.state: RaftState = RaftState.FOLLOWER
        
        # Election timeout (randomized to prevent conflicts)
        self.election_timeout: float = random.uniform(0.15, 0.30)  # 150-300ms
        self.last_heartbeat: float = time.time()
        
        # Heartbeat/replication interval (for leaders)
        self.heartbeat_interval: float = 0.05  # 50ms
        
        # Election tracking
        self.votes_received: int = 0
        self.rpc_client_factory = None  # Will be set by Node

        # Startup grace: delay elections/heartbeats for a short period
        # so peers have time to bring up their RPC servers.
        # Default disabled (0.0) to keep unit tests deterministic;
        # Node can enable and mark readiness.
        self.startup_grace_sec: float = 0.0
        self.rpc_ready_at: float = time.time()
        
        # Apply callback (state machine application for committed entries)
        self.apply_callback = None  # type: Optional[callable]

        # API address hint (set by Node) for redirects
        self.api_host: Optional[str] = None
        self.api_port: Optional[int] = None

        logger.info(f"Raft node {node_id} initialized as {self.state.value} (term {self.current_term})")

    def tick(self) -> None:
        """Advance timers and handle elections/heartbeats."""
        current_time = time.time()

        # If a startup grace period is configured, defer any election/heartbeat
        # activity until our RPC server has been ready for at least that long.
        if self.startup_grace_sec > 0.0:
            if current_time - self.rpc_ready_at < self.startup_grace_sec:
                return
        
        if self.state == RaftState.FOLLOWER:
            # Check if we should start an election
            if current_time - self.last_heartbeat > self.election_timeout:
                self._start_election()
                
        elif self.state == RaftState.CANDIDATE:
            # Check if election timeout expired
            if current_time - self.last_heartbeat > self.election_timeout:
                self._start_election()  # Start new election
                
        elif self.state == RaftState.LEADER:
            # Periodically send AppendEntries (acts as heartbeat and replication)
            if current_time - self.last_heartbeat > self.heartbeat_interval:
                for peer_id in list(self._peers.keys()):
                    asyncio.create_task(self._replicate_to_peer(peer_id))
                self.last_heartbeat = current_time

    def set_startup_grace(self, seconds: float) -> None:
        """Configure startup grace period (seconds)."""
        try:
            self.startup_grace_sec = float(seconds)
        except Exception:
            self.startup_grace_sec = 0.0

    def mark_rpc_ready(self) -> None:
        """Mark the moment when the RPC server is ready to accept calls."""
        self.rpc_ready_at = time.time()

    def _start_election(self) -> None:
        """Start a new election by becoming a candidate."""
        logger.info(f"Node {self.node_id} starting election (term {self.current_term + 1})")
        
        # Transition to candidate
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id  # Vote for ourselves
        self.votes_received = 1  # Count our own vote
        self.last_heartbeat = time.time()
        
        # Reset election timeout
        self.election_timeout = random.uniform(0.15, 0.30)
        
        logger.info(f"Node {self.node_id} is now candidate in term {self.current_term} (1 vote)")
        
        # Send RequestVote to all other nodes
        self._send_request_votes()

    def _send_request_votes(self) -> None:
        """Send RequestVote RPCs to all other nodes."""
        if not self.rpc_client_factory:
            logger.warning("RPC client factory not set, cannot send RequestVote")
            return
            
        for host, port in self.other_nodes:
            # Send RequestVote asynchronously
            asyncio.create_task(self._send_request_vote_to_node(host, port))

    async def _send_request_vote_to_node(self, host: str, port: int) -> None:
        """Send RequestVote RPC to a specific node."""
        try:
            rpc_port = port + 1000  # RPC is on port + 1000
            client = self.rpc_client_factory(host, rpc_port, self.node_id)
            
            response = await client.request_vote(
                candidate_id=self.node_id,
                candidate_term=self.current_term,
                last_log_index=self.last_log_index(),
                last_log_term=self.last_log_term(),
            )
            
            await self._handle_request_vote_response(response, host, port)
            
        except Exception as e:
            logger.error(f"Failed to send RequestVote to {host}:{port}: {e}")

    async def _handle_request_vote_response(self, response: Dict[str, Any], host: str, port: int) -> None:
        """Handle response to RequestVote RPC."""
        if response.get("method") != "request_vote_response":
            logger.warning(f"Unexpected response from {host}:{port}: {response}")
            return
            
        response_term = response.get("term", 0)
        vote_granted = response.get("vote_granted", False)
        
        # If response term is higher, become follower
        if response_term > self.current_term:
            logger.info(f"Received higher term {response_term} from {host}:{port}, becoming follower")
            self.current_term = response_term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
            return
            
        # If we're still a candidate and got a vote
        if self.state == RaftState.CANDIDATE and vote_granted:
            self.votes_received += 1
            logger.info(f"Received vote from {host}:{port}, total votes: {self.votes_received}")
            
            # Check if we have majority
            total_nodes = len(self.other_nodes) + 1  # +1 for ourselves
            majority = (total_nodes // 2) + 1
            
            if self.votes_received >= majority:
                logger.info(f"Node {self.node_id} won election with {self.votes_received}/{total_nodes} votes!")
                self._become_leader()

    def _become_leader(self) -> None:
        """Transition from candidate to leader."""
        self.state = RaftState.LEADER
        self.last_heartbeat = time.time()

        # Initialize leader state
        last_idx = self.last_log_index() + 1
        for host, port in self.other_nodes:
            peer_id = f"{host}:{port}"  # Use host:port as node identifier
            self.next_index[peer_id] = last_idx
            self.match_index[peer_id] = 0

        logger.info(f"Node {self.node_id} is now LEADER in term {self.current_term}")

        # Send initial heartbeats
        self._send_heartbeats()

        # Kick off initial replication attempts (empty entries act as heartbeats)
        for peer_id in list(self._peers.keys()):
            asyncio.create_task(self._replicate_to_peer(peer_id))

    def _send_heartbeats(self) -> None:
        """Send heartbeats to all followers (placeholder for now)."""
        # This will be implemented in Task 2.3 with RequestVote RPC
        logger.debug(f"Leader {self.node_id} sending heartbeats")

    def handle_request_vote(self, candidate_id: str, candidate_term: int, 
                          last_log_index: int, last_log_term: int) -> Dict[str, Any]:
        """Handle RequestVote RPC from a candidate."""
        logger.debug(f"Node {self.node_id} received RequestVote from {candidate_id} (term {candidate_term})")
        
        # If candidate's term is higher, update our term and become follower
        if candidate_term > self.current_term:
            self.current_term = candidate_term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
            logger.info(f"Node {self.node_id} updated to term {candidate_term}, becoming follower")
        
        # Grant vote if:
        # 1. Candidate's term is at least as high as ours
        # 2. We haven't voted for anyone else this term
        # 3. Candidate's log is at least as up-to-date as ours
        vote_granted = (
            candidate_term >= self.current_term and
            (self.voted_for is None or self.voted_for == candidate_id) and
            self._is_candidate_log_up_to_date(last_log_index, last_log_term)
        )
        
        if vote_granted:
            self.voted_for = candidate_id
            self.last_heartbeat = time.time()  # Reset election timeout
            logger.info(f"Node {self.node_id} voted for {candidate_id} in term {candidate_term}")
        else:
            logger.info(f"Node {self.node_id} denied vote to {candidate_id} in term {candidate_term}")
        
        return {
            "term": self.current_term,
            "vote_granted": vote_granted
        }

    def _is_candidate_log_up_to_date(self, last_log_index: int, last_log_term: int) -> bool:
        """Check if candidate's log is at least as up-to-date as ours."""
        # For now, always return True since we don't have logs yet
        # This will be properly implemented in Phase 3
        return True

    def entry_term(self, index: int) -> int:
        if index <= 0:
            return 0
        if index <= len(self.log):
            return self.log[index - 1].term
        # Index beyond log end
        return -1

    def truncate_suffix(self, from_index: int) -> None:
        """Delete log entries from from_index to end (inclusive)."""
        if from_index <= 0:
            self.log.clear()
        elif from_index <= len(self.log):
            del self.log[from_index - 1 :]

    def handle_append_entries(
        self,
        leader_id: str,
        term: int,
        prev_log_index: int,
        prev_log_term: int,
        entries: List[Dict[str, Any]],
        leader_commit: int,
    ) -> Dict[str, Any]:
        """Handle AppendEntries RPC from leader (Phase 3 consistency checks).

        Returns dict with keys: term, success.
        """
        logger.debug(
            f"Node {self.node_id} received AppendEntries from {leader_id} (term {term})"
        )

        # Reply false if term < currentTerm
        if term < self.current_term:
            return {"term": self.current_term, "success": False}

        # If term is newer, update and become follower
        if term > self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.voted_for = None

        # Reset election timeout on any AppendEntries from current leader
        self.last_heartbeat = time.time()

        # Consistency check: if log doesn't contain an entry at prev_log_index
        # whose term matches prev_log_term, reply false
        if prev_log_index > self.last_log_index():
            return {"term": self.current_term, "success": False}
        if prev_log_index > 0 and self.entry_term(prev_log_index) != prev_log_term:
            return {"term": self.current_term, "success": False}

        # If existing entry conflicts with a new one (same index but different term),
        # delete the existing entry and all that follow it
        # Then append any new entries not already in the log
        # prev_log_index is the index of the entry immediately preceding new ones
        new_index = prev_log_index
        for i, ent in enumerate(entries):
            new_index = prev_log_index + 1 + i
            ent_term = int(ent.get("term", 0))
            payload = ent.get("payload", {})
            if new_index <= self.last_log_index():
                if self.entry_term(new_index) != ent_term:
                    # conflict: delete from this index onward
                    self.truncate_suffix(new_index)
                    # append this and the rest
                    self.log.append(LogEntry(index=new_index, term=ent_term, payload=payload))
                    # append remaining entries
                    for j in range(i + 1, len(entries)):
                        idx = prev_log_index + 1 + j
                        e2 = entries[j]
                        self.log.append(
                            LogEntry(index=idx, term=int(e2.get("term", 0)), payload=e2.get("payload", {}))
                        )
                    break
                else:
                    # already present with same term; skip
                    continue
            else:
                # append new entry beyond current end
                self.log.append(LogEntry(index=new_index, term=ent_term, payload=payload))

        # Update commit index
        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, self.last_log_index())

        return {"term": self.current_term, "success": True}

    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information for debugging."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "current_term": self.current_term,
            "voted_for": self.voted_for,
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "log_length": len(self.log),
            "election_timeout": self.election_timeout,
            "time_since_last_heartbeat": time.time() - self.last_heartbeat
        }

    # -------- Phase 3: leader append API (test hook) --------
    def last_log_index(self) -> int:
        return len(self.log)

    def last_log_term(self) -> int:
        return self.log[-1].term if self.log else 0

    def append_local(self, payload: Dict[str, Any]) -> LogEntry:
        """Leader-only: append a new entry to the Raft log.

        For tests in Phase 3. Does not replicate or commit; replication and
        commit will be handled by AppendEntries logic.
        """
        if self.state != RaftState.LEADER:
            raise RuntimeError("append_local requires leader state")
        idx = self.last_log_index() + 1
        entry = LogEntry(index=idx, term=self.current_term, payload=payload)
        self.log.append(entry)
        # Trigger replication to all peers
        if self.state == RaftState.LEADER:
            for peer_id in list(self._peers.keys()):
                asyncio.create_task(self._replicate_to_peer(peer_id))
        # Try to advance commit (single-node majority shortcut)
        self._maybe_advance_commit()
        return entry

    # -------- Leader-side replication (Phase 3) --------
    async def _replicate_to_peer(self, peer_id: str) -> None:
        """Send AppendEntries to a follower based on its nextIndex.

        Retries are handled by subsequent calls (e.g., on timer or next append).
        """
        if not self.rpc_client_factory:
            return
        addr = self._peers.get(peer_id)
        if not addr:
            return
        host, port = addr
        rpc_port = port + 1000
        client = self.rpc_client_factory(host, rpc_port, self.node_id)

        # Determine prev and entries slice
        next_idx = max(1, self.next_index.get(peer_id, self.last_log_index() + 1))
        prev_idx = next_idx - 1
        prev_term = self.entry_term(prev_idx)
        # Entries from next_idx..end
        entries = [
            {"term": e.term, "payload": e.payload}
            for e in self.log[next_idx - 1 :]
        ]

        try:
            resp = await client.append_entries(
                leader_id=self.node_id,
                term=self.current_term,
                prev_log_index=prev_idx,
                prev_log_term=prev_term,
                entries=entries,
                leader_commit=self.commit_index,
                leader_api_host=self.api_host,
                leader_api_port=self.api_port,
            )
        except Exception:
            return

        success = bool(resp.get("success"))
        resp_term = int(resp.get("term", 0))
        if resp_term > self.current_term:
            # Step down
            self.current_term = resp_term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
            return

        if success:
            # If successful: update nextIndex and matchIndex for follower
            match = self.last_log_index()
            self.match_index[peer_id] = match
            self.next_index[peer_id] = match + 1
            self._maybe_advance_commit()
        else:
            # If AppendEntries fails because of log inconsistency: decrement nextIndex and retry later
            self.next_index[peer_id] = max(1, next_idx - 1)

    def _maybe_advance_commit(self) -> None:
        """Advance commitIndex if a majority have replicated an index in current term."""
        if self.state != RaftState.LEADER:
            return
        # Count leader as replicated on its own last_log_index
        total = len(self.other_nodes) + 1
        majority = (total // 2) + 1
        # Try to advance from current commit+1 up to last_log_index
        for idx in range(self.last_log_index(), self.commit_index, -1):
            # Only commit entries from current term (Raft safety)
            if self.entry_term(idx) != self.current_term:
                continue
            replicated = 1  # leader itself
            for peer_id, m in self.match_index.items():
                if m >= idx:
                    replicated += 1
            if replicated >= majority:
                self.commit_index = idx
                self._apply_committed()
                break

    def _apply_committed(self) -> None:
        """Apply entries up to commitIndex to the state machine.

        Calls apply_callback(payload) if configured.
        """
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            payload = self.log[self.last_applied - 1].payload
            cb = getattr(self, "apply_callback", None)
            if cb:
                try:
                    cb(payload)
                except Exception:
                    # Ignore apply errors in core Raft for now
                    pass

    # Public: set the state machine apply callback
    def set_apply_callback(self, cb) -> None:
        self.apply_callback = cb
