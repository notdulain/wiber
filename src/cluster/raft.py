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

# Import commit log for persistent storage
try:
    from src.replication.log import CommitLog
except ImportError:
    # Fallback for testing or if module not available
    CommitLog = None


class RaftState(Enum):
    """Raft node states."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate" 
    LEADER = "leader"


class Raft:
    """Raft consensus algorithm implementation."""
    
    def __init__(self, node_id: str, other_nodes: list = None, log_dir: str = "data"):
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
        
        # Persistent commit log for message storage
        self.commit_log: Optional[CommitLog] = None
        if CommitLog:
            try:
                self.commit_log = CommitLog(log_dir, f"raft-{node_id}")
                logger.info(f"Initialized persistent commit log for node {node_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize commit log: {e}")
                self.commit_log = None
        
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
        """Send AppendEntries (heartbeats) to all followers."""
        if not self.rpc_client_factory:
            logger.warning("RPC client factory not set, cannot send heartbeats")
            return
            
        for host, port in self.other_nodes:
            # Send AppendEntries asynchronously
            asyncio.create_task(self._send_append_entries_to_node(host, port))

    async def _send_append_entries_to_node(self, host: str, port: int) -> None:
        """Send AppendEntries RPC to a specific node."""
        try:
            rpc_port = port + 1000  # RPC is on port + 1000
            client = self.rpc_client_factory(host, rpc_port, self.node_id)
            
            # Calculate prev_log_index and prev_log_term
            prev_log_index = len(self.log)
            prev_log_term = self.log[-1]["term"] if self.log else 0
            
            # Send empty AppendEntries (heartbeat)
            response = await client.append_entries(
                leader_id=self.node_id,
                term=self.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=[],  # Empty entries = heartbeat
                leader_commit=self.commit_index
            )
            
            await self._handle_replication_response(response, host, port, 0)  # 0 entries for heartbeat
            
        except Exception as e:
            logger.error(f"Failed to send AppendEntries to {host}:{port}: {e}")


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
        """Handle AppendEntries RPC from leader."""
        logger.debug(f"Node {self.node_id} received AppendEntries from {leader_id} (term {term})")
        
        # If leader's term is higher, update our term and become follower
        if term > self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
            logger.info(f"Node {self.node_id} updated term to {term}, becoming follower")
        
        # Reset election timeout (heartbeat received)
        self.last_heartbeat = time.time()
        
        # Check log consistency
        success = self._check_log_consistency(prev_log_index, prev_log_term)
        
        if success:
            # Log is consistent, append new entries
            self._append_entries(prev_log_index, entries)
            
            # Update commit index
            self._update_follower_commit_index(leader_commit)
            
            logger.debug(f"Node {self.node_id} successfully appended {len(entries)} entries")
        else:
            logger.debug(f"Node {self.node_id} log consistency check failed")
        
        return {
            "term": self.current_term,
            "success": success
        }

    def _check_log_consistency(self, prev_log_index: int, prev_log_term: int) -> bool:
        """Check if our log is consistent with leader's log up to prev_log_index."""
        # If prev_log_index is 0, log is consistent (no previous entries)
        if prev_log_index == 0:
            return True
        
        # If we don't have enough entries, log is inconsistent
        if prev_log_index > len(self.log):
            logger.debug(f"Log too short: have {len(self.log)}, need {prev_log_index}")
            return False
        
        # Check if the term at prev_log_index matches
        actual_term = self.log[prev_log_index - 1]["term"]  # Log is 0-indexed
        if actual_term != prev_log_term:
            logger.debug(f"Term mismatch at index {prev_log_index}: have {actual_term}, need {prev_log_term}")
            return False
        
        return True

    def _append_entries(self, prev_log_index: int, entries: List[Dict[str, Any]]) -> None:
        """Append new entries to the log, removing any conflicting entries."""
        if not entries:
            return  # Empty AppendEntries (heartbeat)
        
        # Remove any conflicting entries after prev_log_index
        if prev_log_index < len(self.log):
            self.log = self.log[:prev_log_index]
            logger.debug(f"Removed conflicting entries after index {prev_log_index}")
        
        # Append new entries
        for entry in entries:
            self.log.append(entry)
            logger.debug(f"Appended entry: term={entry['term']}, command={entry.get('command', 'unknown')}")

    def _update_follower_commit_index(self, leader_commit: int) -> None:
        """Update commit index and apply committed entries to state machine (for followers)."""
        if leader_commit > self.commit_index:
            old_commit_index = self.commit_index
            self.commit_index = min(leader_commit, len(self.log))
            
            # Apply committed entries to state machine
            self._apply_committed_entries(old_commit_index, self.commit_index)
            
            logger.debug(f"Updated commit index from {old_commit_index} to {self.commit_index}")

    def _apply_committed_entries(self, old_commit_index: int, new_commit_index: int) -> None:
        """Apply committed entries to the state machine."""
        for i in range(old_commit_index, new_commit_index):
            if i < len(self.log):
                entry = self.log[i]
                logger.debug(f"Applying entry {i}: {entry}")
                # TODO: Apply to actual state machine in Phase 4
                # For now, just log the application
                
                # Update last_applied to track what we've applied
                self.last_applied = i + 1  # last_applied is 1-indexed

    def add_entry(self, command: str, data: Dict[str, Any]) -> bool:
        """Add a new entry to the log (only works for leaders)."""
        if self.state != RaftState.LEADER:
            logger.warning(f"Node {self.node_id} is not leader, cannot add entry")
            return False
        
        # Create new log entry
        entry = {
            "term": self.current_term,
            "command": command,
            "data": data,
            "timestamp": time.time()
        }
        
        # Add to in-memory log
        self.log.append(entry)
        
        # Add to persistent commit log if available
        if self.commit_log:
            try:
                offset = self.commit_log.append({
                    "term": self.current_term,
                    "command": command,
                    "data": data,
                    "timestamp": time.time()
                })
                logger.info(f"Leader {self.node_id} added entry to persistent log at offset {offset}: {command} {data}")
            except Exception as e:
                logger.error(f"Failed to write to persistent log: {e}")
        else:
            logger.info(f"Leader {self.node_id} added entry (in-memory only): {command} {data}")
        
        # Replicate to followers
        self._replicate_entry_to_followers()
        
        return True

    def _replicate_entry_to_followers(self) -> None:
        """Replicate the latest entry to all followers."""
        if not self.rpc_client_factory:
            logger.warning("RPC client factory not set, cannot replicate")
            return
        
        for host, port in self.other_nodes:
            asyncio.create_task(self._replicate_to_follower(host, port))

    async def _replicate_to_follower(self, host: str, port: int) -> None:
        """Replicate entries to a specific follower."""
        try:
            rpc_port = port + 1000
            client = self.rpc_client_factory(host, rpc_port, self.node_id)
            node_id = f"{host}:{port}"
            
            # Get the next index for this follower
            next_index = self.next_index.get(node_id, len(self.log))
            
            # Prepare entries to send
            entries_to_send = []
            if next_index <= len(self.log):
                entries_to_send = self.log[next_index - 1:]  # Send from next_index onwards
            
            # Calculate prev_log_index and prev_log_term
            prev_log_index = next_index - 1
            prev_log_term = self.log[prev_log_index - 1]["term"] if prev_log_index > 0 else 0
            
            # Send AppendEntries
            response = await client.append_entries(
                leader_id=self.node_id,
                term=self.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries_to_send,
                leader_commit=self.commit_index
            )
            
            await self._handle_replication_response(response, host, port, len(entries_to_send))
            
        except Exception as e:
            logger.error(f"Failed to replicate to {host}:{port}: {e}")

    async def _handle_replication_response(self, response: Dict[str, Any], host: str, port: int, entries_sent: int) -> None:
        """Handle response from replication attempt."""
        if response.get("method") != "append_entries_response":
            logger.warning(f"Unexpected response from {host}:{port}: {response}")
            return
        
        node_id = f"{host}:{port}"
        response_term = response.get("term", 0)
        success = response.get("success", False)
        
        # If response term is higher, become follower
        if response_term > self.current_term:
            logger.info(f"Received higher term {response_term} from {host}:{port}, becoming follower")
            self.current_term = response_term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
            return
        
        if success:
            # Follower accepted our entries
            if node_id in self.next_index:
                self.next_index[node_id] += entries_sent
            if node_id in self.match_index:
                self.match_index[node_id] = self.next_index[node_id] - 1
            
            logger.debug(f"Follower {node_id} accepted {entries_sent} entries, next_index={self.next_index[node_id]}")
            
            # Check if we can commit more entries
            self._update_commit_index()
        else:
            # Follower rejected our entries, decrement next_index
            if node_id in self.next_index and self.next_index[node_id] > 0:
                self.next_index[node_id] -= 1
            logger.debug(f"Follower {node_id} rejected entries, decremented next_index to {self.next_index[node_id]}")

    def _update_commit_index(self) -> None:
        """Update commit index based on majority replication."""
        # Find the highest index that has been replicated to majority
        for i in range(len(self.log), self.commit_index, -1):
            if i == 0:
                continue
            
            # Count how many followers have this entry
            count = 1  # Count ourselves
            for node_id in self.match_index:
                if self.match_index[node_id] >= i:
                    count += 1
            
            # Check if we have majority
            total_nodes = len(self.other_nodes) + 1
            majority = (total_nodes // 2) + 1
            
            if count >= majority:
                # We can commit this entry
                old_commit_index = self.commit_index
                self.commit_index = i
                
                if self.commit_index > old_commit_index:
                    logger.info(f"Leader {self.node_id} committed entries up to index {self.commit_index}")
                    self._apply_committed_entries(old_commit_index, self.commit_index)
                break

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
            "time_since_last_heartbeat": time.time() - self.last_heartbeat,
            "next_index": self.next_index.copy() if self.state == RaftState.LEADER else {},
            "match_index": self.match_index.copy() if self.state == RaftState.LEADER else {}
        }

    def get_log_info(self) -> Dict[str, Any]:
        """Get detailed log information for debugging."""
        return {
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "entries": [
                {
                    "index": i + 1,  # 1-indexed
                    "term": entry["term"],
                    "command": entry.get("command", "unknown"),
                    "data": entry.get("data", {}),
                    "committed": i < self.commit_index,
                    "applied": i < self.last_applied
                }
                for i, entry in enumerate(self.log)
            ]
        }

