"""Node process entry and orchestration.

Responsibilities:
- Initialize consensus (Raft) and RPC server
- Start client-facing API (wire protocol)
- Manage replication log and dedup cache
- Manage topics and message storage
"""

from __future__ import annotations

import asyncio
from typing import Optional

from api.wire import create_api_server, set_topic_manager
from cluster.rpc import RpcServer, RpcClient
from cluster.raft import Raft

# Import topic management
try:
    from replication.topics import TopicManager
except ImportError:
    TopicManager = None


class Node:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0, 
                 other_nodes: list = None, log_dir: str = "data"):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.other_nodes = other_nodes or []  # List of (host, port) tuples
        self.log_dir = log_dir
        self._api_server: Optional[asyncio.AbstractServer] = None
        self._rpc_server: Optional[RpcServer] = None
        self._raft: Optional[Raft] = None
        self._topic_manager: Optional[TopicManager] = None

    def start(self) -> None:
        """Start node services (consensus, API, replication)."""
        try:
            asyncio.run(self._start_async())
        except KeyboardInterrupt:
            print(f"\nNode {self.node_id} shutting down...")

    async def _start_async(self) -> None:
        try:
            # Initialize topic manager
            if TopicManager:
                self._topic_manager = TopicManager(self.log_dir, enable_dedup=True)
                # Create default topics
                self._topic_manager.create_topic("notifications", "User notifications", 24, 100)
                self._topic_manager.create_topic("logs", "System logs", 48, 500)
                self._topic_manager.create_topic("events", "Application events", 72, 300)
                print(f"[OK] Topic manager initialized with {len(self._topic_manager.topics)} topics")
            else:
                print(f"[WARNING] TopicManager not available, using basic API only")
            
            # Initialize Raft consensus
            self._raft = Raft(self.node_id, self.other_nodes, log_dir=self.log_dir)
            
            # Provide RPC client factory to Raft
            self._raft.rpc_client_factory = lambda host, port, node_id: RpcClient(host, port, node_id)
            
            # Set topic manager for wire protocol
            if self._topic_manager:
                set_topic_manager(self._topic_manager, self._raft)
            
            # Start API server (for clients)
            self._api_server = await create_api_server(self.host, self.port)
            
            # Start RPC server (for other nodes) on port + 1000
            rpc_port = self.port + 1000
            self._rpc_server = RpcServer(self.host, rpc_port, self.node_id, self._raft)
            await self._rpc_server.start()
            
            print(f"Node {self.node_id} started:")
            print(f"  API server: {self.host}:{self.port} (PING/PUB/SUB/HISTORY)")
            print(f"  RPC server: {self.host}:{rpc_port} (inter-node communication)")
            print(f"  Raft state: {self._raft.state.value} (term {self._raft.current_term})")
            if self._topic_manager:
                print(f"  Topics: {', '.join(self._topic_manager.topics.keys())}")
            print("Press Ctrl+C to stop")
            
            # Run both servers concurrently with Raft ticking
            async with self._api_server:
                await asyncio.gather(
                    self._api_server.serve_forever(),
                    self._raft_tick_loop()
                )
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                print(f"ERROR: Port {self.port} is already in use for node {self.node_id}")
                print("Make sure no other instances are running")
                raise
            else:
                raise

    async def _raft_tick_loop(self) -> None:
        """Raft consensus tick loop."""
        while True:
            if self._raft:
                self._raft.tick()
            await asyncio.sleep(0.01)  # Tick every 10ms

    async def ping_other_node(self, other_host: str, other_port: int) -> dict:
        """Ping another node via RPC."""
        rpc_port = other_port + 1000  # RPC is on port + 1000
        client = RpcClient(other_host, rpc_port, self.node_id)
        return await client.ping()

