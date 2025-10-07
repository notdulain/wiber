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
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class RaftState(Enum):
    """Raft node states."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate" 
    LEADER = "leader"


class Raft:
    """Raft consensus algorithm implementation."""
    
    def __init__(self, node_id: str, other_nodes: list = None):
        self.node_id = node_id
        self.other_nodes = other_nodes or []  # List of (host, port) tuples
        
        # Persistent state (survives crashes)
        self.current_term: int = 0
        self.voted_for: Optional[str] = None  # None, or node_id of candidate voted for
        self.log: List[Dict[str, Any]] = []  # Will be used in Phase 3
        
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
        
        # Heartbeat interval (for leaders)
        self.heartbeat_interval: float = 0.05  # 50ms
        
        # Election tracking
        self.votes_received: int = 0
        self.rpc_client_factory = None  # Will be set by Node
        
        logger.info(f"Raft node {node_id} initialized as {self.state.value} (term {self.current_term})")

    def tick(self) -> None:
        """Advance timers and handle elections/heartbeats."""
        current_time = time.time()
        
        if self.state == RaftState.FOLLOWER:
            # Check if we should start an election
            if current_time - self.last_heartbeat > self.election_timeout:
                self._start_election()
                
        elif self.state == RaftState.CANDIDATE:
            # Check if election timeout expired
            if current_time - self.last_heartbeat > self.election_timeout:
                self._start_election()  # Start new election
                
        elif self.state == RaftState.LEADER:
            # Send heartbeats to followers
            if current_time - self.last_heartbeat > self.heartbeat_interval:
                self._send_heartbeats()
                self.last_heartbeat = current_time

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
                last_log_index=len(self.log),
                last_log_term=self.log[-1]["term"] if self.log else 0
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
        for host, port in self.other_nodes:
            node_id = f"{host}:{port}"  # Use host:port as node identifier
            self.next_index[node_id] = len(self.log) + 1
            self.match_index[node_id] = 0
            
        logger.info(f"Node {self.node_id} is now LEADER in term {self.current_term}")
        
        # Send initial heartbeats
        self._send_heartbeats()

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

    def handle_append_entries(self, leader_id: str, term: int, prev_log_index: int,
                            prev_log_term: int, entries: List[Dict[str, Any]], 
                            leader_commit: int) -> Dict[str, Any]:
        """Handle AppendEntries RPC from leader (placeholder for Phase 3)."""
        logger.debug(f"Node {self.node_id} received AppendEntries from {leader_id} (term {term})")
        
        # If leader's term is higher, update our term and become follower
        if term > self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
        
        # Reset election timeout
        self.last_heartbeat = time.time()
        
        return {
            "term": self.current_term,
            "success": True  # Placeholder - will be implemented in Phase 3
        }

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

