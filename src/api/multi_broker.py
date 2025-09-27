import asyncio
import json
import time
import uuid
import random
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from enum import Enum
from ..config.settings import HOST, PORT
from ..database.storage import append_message, read_last

# Multi-Broker Architecture with Raft Consensus
# This implements a distributed messaging system with:
# 1. Leader election using Raft consensus
# 2. Log replication across multiple brokers
# 3. Automatic failover and recovery
# 4. Client routing to current leader

class NodeRole(Enum):
    """Raft node roles"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

@dataclass
class LogEntry:
    """Raft log entry"""
    term: int
    index: int
    command: str
    data: Dict[str, Any]
    timestamp: float

@dataclass
class VoteRequest:
    """Raft vote request"""
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int

@dataclass
class VoteResponse:
    """Raft vote response"""
    term: int
    vote_granted: bool

@dataclass
class AppendEntriesRequest:
    """Raft append entries request"""
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int

@dataclass
class AppendEntriesResponse:
    """Raft append entries response"""
    term: int
    success: bool
    next_index: int

class RaftConsensus:
    """Raft consensus implementation for multi-broker coordination"""
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.role = NodeRole.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader-specific state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Election and heartbeat timers
        self.election_timeout = random.uniform(5.0, 10.0)  # Random timeout to avoid split votes
        self.heartbeat_interval = 1.0
        self.last_heartbeat = time.time()
        self.last_election_time = time.time()
        
        # RPC communication
        self.rpc_connections: Dict[str, tuple] = {}  # peer_id -> (reader, writer)
        
    async def start(self):
        """Start the Raft consensus process"""
        print(f"[{self.node_id}] Starting Raft consensus (peers: {self.peers})")
        
        # Start background tasks
        asyncio.create_task(self._election_timer())
        asyncio.create_task(self._heartbeat_timer())
        
    async def _election_timer(self):
        """Election timer - triggers new election if no leader heartbeat"""
        while True:
            try:
                await asyncio.sleep(0.1)  # Check frequently
                
                current_time = time.time()
                
                if self.role == NodeRole.FOLLOWER:
                    # Check if we should start an election
                    if current_time - self.last_heartbeat > self.election_timeout:
                        print(f"[{self.node_id}] Election timeout, starting new election")
                        await self._start_election()
                        
                elif self.role == NodeRole.CANDIDATE:
                    # Check if election is taking too long
                    if current_time - self.last_election_time > self.election_timeout * 2:
                        print(f"[{self.node_id}] Election timeout, restarting election")
                        await self._start_election()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.node_id}] Error in election timer: {e}")
                await asyncio.sleep(1.0)
    
    async def _heartbeat_timer(self):
        """Heartbeat timer - sends heartbeats if leader"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.role == NodeRole.LEADER:
                    await self._send_heartbeats()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.node_id}] Error in heartbeat timer: {e}")
                await asyncio.sleep(1.0)
    
    async def _start_election(self):
        """Start a new election"""
        print(f"[{self.node_id}] Starting election for term {self.current_term + 1}")
        
        self.role = NodeRole.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_election_time = time.time()
        
        # Request votes from all peers
        votes_received = 1  # Vote for ourselves
        total_nodes = len(self.peers) + 1
        
        for peer in self.peers:
            try:
                vote_request = VoteRequest(
                    term=self.current_term,
                    candidate_id=self.node_id,
                    last_log_index=len(self.log),
                    last_log_term=self.log[-1].term if self.log else 0
                )
                
                response = await self._send_vote_request(peer, vote_request)
                if response and response.vote_granted:
                    votes_received += 1
                    
            except Exception as e:
                print(f"[{self.node_id}] Failed to request vote from {peer}: {e}")
        
        # Check if we won the election
        if votes_received > total_nodes // 2:
            print(f"[{self.node_id}] Won election! Becoming leader for term {self.current_term}")
            await self._become_leader()
        else:
            print(f"[{self.node_id}] Lost election. Remaining follower.")
            self.role = NodeRole.FOLLOWER
    
    async def _become_leader(self):
        """Transition to leader role"""
        self.role = NodeRole.LEADER
        
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log) + 1
            self.match_index[peer] = 0
        
        print(f"[{self.node_id}] Now leader of term {self.current_term}")
    
    async def _send_heartbeats(self):
        """Send heartbeats to all followers"""
        for peer in self.peers:
            try:
                request = AppendEntriesRequest(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=0,
                    prev_log_term=0,
                    entries=[],  # Empty entries = heartbeat
                    leader_commit=self.commit_index
                )
                
                await self._send_append_entries(peer, request)
                
            except Exception as e:
                print(f"[{self.node_id}] Failed to send heartbeat to {peer}: {e}")
    
    async def _send_vote_request(self, peer: str, request: VoteRequest) -> Optional[VoteResponse]:
        """Send vote request to a peer (simplified - in real implementation would be RPC)"""
        # For this simplified implementation, we'll simulate the response
        # In a real system, this would be an actual RPC call over the network
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        # Simulate vote response (simplified logic)
        if request.term >= self.current_term:
            return VoteResponse(term=request.term, vote_granted=True)
        else:
            return VoteResponse(term=self.current_term, vote_granted=False)
    
    async def _send_append_entries(self, peer: str, request: AppendEntriesRequest) -> Optional[AppendEntriesResponse]:
        """Send append entries to a peer (simplified - in real implementation would be RPC)"""
        # For this simplified implementation, we'll simulate the response
        # In a real system, this would be an actual RPC call over the network
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        # Simulate append entries response
        return AppendEntriesResponse(
            term=request.term,
            success=True,
            next_index=len(self.log) + 1
        )
    
    async def handle_vote_request(self, request: VoteRequest) -> VoteResponse:
        """Handle vote request from another candidate"""
        print(f"[{self.node_id}] Received vote request from {request.candidate_id} for term {request.term}")
        
        if request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = None
            self.role = NodeRole.FOLLOWER
        
        # Check if we can vote for this candidate
        can_vote = (
            (self.voted_for is None or self.voted_for == request.candidate_id) and
            request.term >= self.current_term and
            request.last_log_index >= len(self.log)
        )
        
        if can_vote:
            self.voted_for = request.candidate_id
            self.last_heartbeat = time.time()
            print(f"[{self.node_id}] Voting for {request.candidate_id}")
            return VoteResponse(term=request.term, vote_granted=True)
        else:
            print(f"[{self.node_id}] Rejecting vote for {request.candidate_id}")
            return VoteResponse(term=self.current_term, vote_granted=False)
    
    async def handle_append_entries(self, request: AppendEntriesRequest) -> AppendEntriesResponse:
        """Handle append entries from leader"""
        print(f"[{self.node_id}] Received append entries from {request.leader_id} for term {request.term}")
        
        if request.term >= self.current_term:
            self.current_term = request.term
            self.role = NodeRole.FOLLOWER
            self.last_heartbeat = time.time()
            
            # In a real implementation, we would apply the log entries here
            # For now, we'll just simulate success
            
            return AppendEntriesResponse(
                term=request.term,
                success=True,
                next_index=len(self.log) + 1
            )
        else:
            return AppendEntriesResponse(
                term=self.current_term,
                success=False,
                next_index=len(self.log) + 1
            )
    
    async def append_log_entry(self, command: str, data: Dict[str, Any]) -> bool:
        """Append a new log entry (only leader can do this)"""
        if self.role != NodeRole.LEADER:
            return False
        
        # Create new log entry
        entry = LogEntry(
            term=self.current_term,
            index=len(self.log) + 1,
            command=command,
            data=data,
            timestamp=time.time()
        )
        
        # Add to local log
        self.log.append(entry)
        
        # Replicate to followers (simplified)
        for peer in self.peers:
            try:
                request = AppendEntriesRequest(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=entry.index - 1,
                    prev_log_term=self.log[entry.index - 2].term if entry.index > 1 else 0,
                    entries=[entry],
                    leader_commit=self.commit_index
                )
                
                response = await self._send_append_entries(peer, request)
                if response and response.success:
                    self.match_index[peer] = entry.index
                    self.next_index[peer] = entry.index + 1
                    
            except Exception as e:
                print(f"[{self.node_id}] Failed to replicate to {peer}: {e}")
        
        # Check if we can commit this entry
        if await self._can_commit_entry(entry.index):
            self.commit_index = entry.index
            await self._apply_committed_entries()
        
        return True
    
    async def _can_commit_entry(self, index: int) -> bool:
        """Check if an entry can be committed (majority of followers have it)"""
        committed_count = 1  # We have it locally
        
        for peer in self.peers:
            if self.match_index.get(peer, 0) >= index:
                committed_count += 1
        
        return committed_count > len(self.peers) // 2
    
    async def _apply_committed_entries(self):
        """Apply committed log entries to state machine"""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            if self.last_applied <= len(self.log):
                entry = self.log[self.last_applied - 1]
                await self._apply_log_entry(entry)
    
    async def _apply_log_entry(self, entry: LogEntry):
        """Apply a single log entry to the state machine"""
        print(f"[{self.node_id}] Applying log entry {entry.index}: {entry.command}")
        # In a real implementation, this would update the broker's state
        # For now, we'll just log it

class MultiBroker:
    """Multi-broker implementation with Raft consensus"""
    
    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        
        # Raft consensus
        self.raft = RaftConsensus(node_id, peers)
        
        # Broker state (similar to single broker)
        self.subscriptions: Dict[str, Set[asyncio.StreamWriter]] = {}
        self.consumer_groups: Dict[str, Dict[str, List[asyncio.StreamWriter]]] = {}
        self.clients: Set[asyncio.StreamWriter] = set()
        self.group_counters: Dict[str, int] = {}
        
        # ACK and heartbeat state
        self.pending_messages: Dict[asyncio.StreamWriter, List[Dict]] = {}
        self.ack_timeouts: Dict[str, float] = {}
        self.last_heartbeat: Dict[asyncio.StreamWriter, float] = {}
        
        # DLQ state
        self.message_retry_count: Dict[str, int] = {}
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]
        
        # Multi-broker specific state
        self.cluster_state: Dict[str, Any] = {}
        self.partition_leaders: Dict[str, str] = {}
        
    async def start(self):
        """Start the multi-broker node"""
        print(f"[{self.node_id}] Starting multi-broker on port {self.port}")
        
        # Start Raft consensus
        await self.raft.start()
        
        # Start server
        server = await asyncio.start_server(
            self._handle_client, HOST, self.port
        )
        
        addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        print(f"[{self.node_id}] Multi-broker listening on {addr}")
        
        # Start monitoring tasks
        ack_monitor_task = asyncio.create_task(self._monitor_ack_timeouts())
        heartbeat_monitor_task = asyncio.create_task(self._monitor_heartbeats())
        dlq_monitor_task = asyncio.create_task(self._monitor_dlq_retries())
        
        try:
            async with server:
                await server.serve_forever()
        finally:
            ack_monitor_task.cancel()
            heartbeat_monitor_task.cancel()
            dlq_monitor_task.cancel()
            try:
                await ack_monitor_task
                await heartbeat_monitor_task
                await dlq_monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle client connections"""
        client_addr = writer.get_extra_info('peername')
        self.clients.add(writer)
        self.last_heartbeat[writer] = time.time()
        
        print(f"[{self.node_id}] Client connected: {client_addr}")
        await self._send_line(writer, "OK connected")
        
        try:
            while not reader.at_eof():
                raw = await reader.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                
                try:
                    await self._handle_command(reader, writer, line)
                except Exception as e:
                    await self._send_line(writer, f"ERR {type(e).__name__}: {e}")
        finally:
            self._disconnect(writer)
            print(f"[{self.node_id}] Client disconnected: {client_addr}")
    
    async def _handle_command(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, line: str):
        """Handle client commands"""
        if line.upper() == "PING":
            await self._send_line(writer, "OK pong")
            return
            
        if line.upper() == "QUIT":
            await self._send_line(writer, "OK bye")
            writer.close()
            await writer.wait_closed()
            return
        
        if line.startswith("STATUS"):
            await self._handle_status(writer)
            return
        
        if line.startswith("SUB "):
            await self._handle_subscribe(writer, line)
            return
        
        if line.startswith("PUB "):
            await self._handle_publish(writer, line)
            return
        
        if line.startswith("HISTORY "):
            await self._handle_history(writer, line)
            return
        
        if line.startswith("ACK "):
            await self._handle_ack(writer, line)
            return
        
        if line.upper() == "HEARTBEAT":
            await self._handle_heartbeat(writer)
            return
        
        await self._send_line(writer, f"ERR unknown command: {line}")
    
    async def _handle_status(self, writer: asyncio.StreamWriter):
        """Handle status request"""
        status = {
            "node_id": self.node_id,
            "role": self.raft.role.value,
            "term": self.raft.current_term,
            "log_length": len(self.raft.log),
            "commit_index": self.raft.commit_index,
            "peers": self.peers,
            "clients_connected": len(self.clients)
        }
        await self._send_line(writer, f"STATUS {json.dumps(status)}")
    
    async def _handle_subscribe(self, writer: asyncio.StreamWriter, line: str):
        """Handle subscription requests"""
        parts = line.split()
        if len(parts) < 2:
            await self._send_line(writer, "ERR usage: SUB <topic> [group_id]")
            return
        
        topic = parts[1]
        group_id = parts[2] if len(parts) > 2 else None
        
        if group_id:
            self._subscribe_to_group(topic, group_id, writer)
            await self._send_line(writer, f"OK subscribed {topic} in group {group_id}")
        else:
            self._subscribe(topic, writer)
            await self._send_line(writer, f"OK subscribed {topic}")
    
    async def _handle_publish(self, writer: asyncio.StreamWriter, line: str):
        """Handle publish requests - only leader can accept publishes"""
        if self.raft.role != NodeRole.LEADER:
            await self._send_line(writer, "ERR not leader")
            return
        
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            await self._send_line(writer, "ERR usage: PUB <topic> <message>")
            return
        
        topic, message = parts[1], parts[2]
        ts = time.time()
        
        # Create log entry for the publish command
        log_data = {
            "topic": topic,
            "message": message,
            "timestamp": ts
        }
        
        # Append to Raft log
        success = await self.raft.append_log_entry("PUBLISH", log_data)
        
        if success:
            # Store message locally
            append_message(topic, ts, message)
            
            # Get the message we just stored
            records = read_last(topic, 1)
            if records:
                record = records[0]
                message_id = record.get("id", "")
                offset = record.get("offset", 0)
                await self._broadcast(topic, message_id, offset, ts, message)
            
            await self._send_line(writer, "OK published")
        else:
            await self._send_line(writer, "ERR failed to replicate message")
    
    async def _handle_history(self, writer: asyncio.StreamWriter, line: str):
        """Handle history requests"""
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            await self._send_line(writer, "ERR usage: HISTORY <topic> <n>")
            return
        
        topic, n_str = parts[1], parts[2]
        try:
            n = int(n_str)
        except ValueError:
            await self._send_line(writer, "ERR n must be an integer")
            return
        
        records = read_last(topic, n)
        for rec in records:
            message_id = rec.get("id", "")
            offset = rec.get("offset", 0)
            ts = rec.get("ts")
            msg = rec.get("msg", "")
            await self._send_line(writer, f"HISTORY {topic} {message_id} {offset} {ts} {msg}")
        
        await self._send_line(writer, "OK history end")
    
    async def _handle_ack(self, writer: asyncio.StreamWriter, line: str):
        """Handle acknowledgment from consumer"""
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            await self._send_line(writer, "ERR usage: ACK <message_id>")
            return
        
        message_id = parts[1]
        await self._send_line(writer, f"OK ack_received {message_id}")
    
    async def _handle_heartbeat(self, writer: asyncio.StreamWriter):
        """Handle heartbeat from consumer"""
        self.last_heartbeat[writer] = time.time()
        await self._send_line(writer, "OK heartbeat_received")
    
    def _subscribe(self, topic: str, writer: asyncio.StreamWriter) -> None:
        """Subscribe a client to a topic"""
        self.subscriptions.setdefault(topic, set()).add(writer)
        print(f"[{self.node_id}] Client subscribed to {topic}")
    
    def _subscribe_to_group(self, topic: str, group_id: str, writer: asyncio.StreamWriter) -> None:
        """Subscribe a client to a consumer group for a topic"""
        if topic not in self.consumer_groups:
            self.consumer_groups[topic] = {}
        if group_id not in self.consumer_groups[topic]:
            self.consumer_groups[topic][group_id] = []
        
        self.consumer_groups[topic][group_id].append(writer)
        print(f"[{self.node_id}] Client joined group '{group_id}' for topic '{topic}'")
    
    def _disconnect(self, writer: asyncio.StreamWriter) -> None:
        """Handle client disconnection"""
        # Remove from subscriptions
        for subs in self.subscriptions.values():
            subs.discard(writer)
        
        # Remove from consumer groups
        for topic_groups in self.consumer_groups.values():
            for group_consumers in topic_groups.values():
                if writer in group_consumers:
                    group_consumers.remove(writer)
        
        # Clean up state
        if writer in self.pending_messages:
            del self.pending_messages[writer]
        if writer in self.last_heartbeat:
            del self.last_heartbeat[writer]
        
        self.clients.discard(writer)
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass
    
    async def _broadcast(self, topic: str, message_id: str, offset: int, ts: float, message: str) -> None:
        """Broadcast message to subscribers"""
        line = f"MSG {topic} {message_id} {offset} {ts} {message}"
        dead: Set[asyncio.StreamWriter] = set()
        
        # Send to regular subscribers
        for w in self.subscriptions.get(topic, set()):
            try:
                await self._send_line(w, line)
            except Exception:
                dead.add(w)
        
        # Send to consumer groups
        await self._distribute_to_groups(topic, line, dead)
        
        # Clean up dead connections
        for w in dead:
            self._disconnect(w)
    
    async def _distribute_to_groups(self, topic: str, line: str, dead: Set[asyncio.StreamWriter]) -> None:
        """Distribute messages to consumer groups"""
        if topic not in self.consumer_groups:
            return
        
        # Extract message info
        parts = line.split(maxsplit=5)
        if len(parts) >= 5:
            message_id = parts[2]
            offset = int(parts[3])
            ts = float(parts[4])
            message = parts[5] if len(parts) > 5 else ""
        else:
            return
        
        for group_id, consumers in self.consumer_groups[topic].items():
            if not consumers:
                continue
            
            # Find available consumer
            available_consumers = [
                c for c in consumers 
                if len(self.pending_messages.get(c, [])) < 5
            ]
            
            if not available_consumers:
                continue
            
            # Round-robin selection
            group_key = f"{topic}:{group_id}"
            if group_key not in self.group_counters:
                self.group_counters[group_key] = 0
            
            consumer_index = self.group_counters[group_key] % len(available_consumers)
            target_consumer = available_consumers[consumer_index]
            
            try:
                await self._send_line(target_consumer, line)
                
                # Track pending message
                message_data = {
                    "id": message_id,
                    "offset": offset,
                    "ts": ts,
                    "msg": message,
                    "topic": topic,
                    "group_id": group_id,
                    "sent_time": time.time()
                }
                
                if target_consumer not in self.pending_messages:
                    self.pending_messages[target_consumer] = []
                self.pending_messages[target_consumer].append(message_data)
                self.ack_timeouts[message_id] = time.time()
                
            except Exception:
                dead.add(target_consumer)
            
            self.group_counters[group_key] += 1
    
    async def _monitor_ack_timeouts(self) -> None:
        """Monitor for ACK timeouts"""
        while True:
            try:
                current_time = time.time()
                timed_out_messages = []
                
                for message_id, sent_time in self.ack_timeouts.items():
                    if current_time - sent_time > 30.0:  # 30 second timeout
                        timed_out_messages.append(message_id)
                
                for message_id in timed_out_messages:
                    await self._handle_ack_timeout(message_id)
                
                await asyncio.sleep(5.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.node_id}] Error in ACK timeout monitor: {e}")
                await asyncio.sleep(5.0)
    
    async def _handle_ack_timeout(self, message_id: str) -> None:
        """Handle ACK timeout"""
        print(f"[{self.node_id}] ACK timeout for message {message_id}")
        
        for consumer, pending in self.pending_messages.items():
            for i, msg in enumerate(pending):
                if msg["id"] == message_id:
                    timed_out_msg = pending.pop(i)
                    if message_id in self.ack_timeouts:
                        del self.ack_timeouts[message_id]
                    await self._handle_message_retry_or_dlq(timed_out_msg)
                    return
        
        if message_id in self.ack_timeouts:
            del self.ack_timeouts[message_id]
    
    async def _monitor_heartbeats(self) -> None:
        """Monitor for heartbeat timeouts"""
        while True:
            try:
                current_time = time.time()
                dead_consumers = []
                
                for consumer, last_heartbeat_time in self.last_heartbeat.items():
                    if current_time - last_heartbeat_time > 30.0:  # 30 second timeout
                        dead_consumers.append(consumer)
                
                for dead_consumer in dead_consumers:
                    await self._handle_dead_consumer(dead_consumer)
                
                await asyncio.sleep(5.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.node_id}] Error in heartbeat monitor: {e}")
                await asyncio.sleep(5.0)
    
    async def _handle_dead_consumer(self, dead_consumer: asyncio.StreamWriter) -> None:
        """Handle dead consumer"""
        print(f"[{self.node_id}] Consumer detected as dead")
        
        if dead_consumer in self.pending_messages:
            pending_messages = self.pending_messages[dead_consumer]
            print(f"[{self.node_id}] Redistributing {len(pending_messages)} pending messages")
            
            for msg in pending_messages:
                topic = msg.get("topic")
                group_id = msg.get("group_id")
                
                if topic and group_id and topic in self.consumer_groups:
                    if group_id in self.consumer_groups[topic]:
                        alive_consumers = [
                            c for c in self.consumer_groups[topic][group_id]
                            if c != dead_consumer and c in self.last_heartbeat
                        ]
                        
                        if alive_consumers:
                            target_consumer = alive_consumers[0]
                            message_line = f"MSG {topic} {msg['id']} {msg['offset']} {msg['ts']} {msg['msg']}"
                            
                            try:
                                await self._send_line(target_consumer, message_line)
                                if target_consumer not in self.pending_messages:
                                    self.pending_messages[target_consumer] = []
                                self.pending_messages[target_consumer].append(msg)
                                self.ack_timeouts[msg['id']] = time.time()
                            except Exception as e:
                                print(f"[{self.node_id}] Failed to redistribute message: {e}")
        
        self._disconnect(dead_consumer)
    
    async def _handle_message_retry_or_dlq(self, message: Dict) -> None:
        """Handle message retry or DLQ"""
        message_id = message["id"]
        retry_count = self.message_retry_count.get(message_id, 0)
        
        if retry_count < self.max_retries:
            retry_count += 1
            self.message_retry_count[message_id] = retry_count
            
            delay = self.retry_delays[min(retry_count - 1, len(self.retry_delays) - 1)]
            print(f"[{self.node_id}] Retrying message {message_id} after {delay}s")
            
            asyncio.create_task(self._retry_message_with_delay(message, delay))
        else:
            print(f"[{self.node_id}] Sending message {message_id} to DLQ")
            await self._send_to_dlq(message)
    
    async def _retry_message_with_delay(self, message: Dict, delay: float) -> None:
        """Retry message with delay"""
        await asyncio.sleep(delay)
        
        topic = message["topic"]
        group_id = message["group_id"]
        
        if topic in self.consumer_groups and group_id in self.consumer_groups[topic]:
            alive_consumers = [
                c for c in self.consumer_groups[topic][group_id]
                if c in self.last_heartbeat
            ]
            
            if alive_consumers:
                target_consumer = alive_consumers[0]
                message_line = f"MSG {topic} {message['id']} {message['offset']} {message['ts']} {message['msg']}"
                
                try:
                    await self._send_line(target_consumer, message_line)
                    if target_consumer not in self.pending_messages:
                        self.pending_messages[target_consumer] = []
                    self.pending_messages[target_consumer].append(message)
                    self.ack_timeouts[message['id']] = time.time()
                except Exception as e:
                    print(f"[{self.node_id}] Failed to retry message: {e}")
                    await self._send_to_dlq(message)
            else:
                await self._send_to_dlq(message)
    
    async def _send_to_dlq(self, message: Dict) -> None:
        """Send message to Dead Letter Queue"""
        dlq_topic = f"{message['topic']}.dlq"
        
        dlq_message = {
            "id": message["id"],
            "offset": message["offset"],
            "ts": message["ts"],
            "msg": message["msg"],
            "original_topic": message["topic"],
            "retry_count": self.message_retry_count.get(message["id"], 0),
            "dlq_timestamp": time.time(),
            "failure_reason": "max_retries_exceeded"
        }
        
        append_message(dlq_topic, dlq_message["dlq_timestamp"], str(dlq_message))
        
        if message["id"] in self.message_retry_count:
            del self.message_retry_count[message["id"]]
        
        print(f"[{self.node_id}] Message {message['id']} sent to DLQ")
    
    async def _monitor_dlq_retries(self) -> None:
        """Monitor DLQ retries"""
        while True:
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.node_id}] Error in DLQ monitor: {e}")
                await asyncio.sleep(10.0)
    
    @staticmethod
    async def _send_line(writer: asyncio.StreamWriter, line: str) -> None:
        """Send a line to a client"""
        writer.write((line + "\n").encode("utf-8"))
        try:
            await writer.drain()
        except ConnectionResetError:
            pass

async def main():
    """Main function for multi-broker"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Broker Wiber')
    parser.add_argument('--node-id', required=True, help='Unique node identifier')
    parser.add_argument('--port', type=int, default=8000, help='Port to listen on')
    parser.add_argument('--peers', help='Comma-separated list of peer addresses')
    
    args = parser.parse_args()
    
    peers = []
    if args.peers:
        peers = [peer.strip() for peer in args.peers.split(',')]
    
    broker = MultiBroker(args.node_id, args.port, peers)
    await broker.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMulti-broker stopped by user")
