"""Node process entry and orchestration.

Responsibilities:
- Initialize consensus (Raft) and RPC server
- Start client-facing API (wire protocol)
- Manage replication log and dedup cache
"""

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Set

from api.wire import create_api_server
from cluster.rpc import RpcServer, RpcClient
from cluster.raft import Raft
from replication.dedup import DedupCache
from replication.log import CommitLog


class Node:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0, 
                 other_nodes: list = None, data_dir: str = ".data", startup_grace: float = 0.5):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.other_nodes = other_nodes or []  # List of (host, port) tuples
        self._api_server: Optional[asyncio.AbstractServer] = None
        self._rpc_server: Optional[RpcServer] = None
        self._raft: Optional[Raft] = None
        self._log = CommitLog(base_dir=data_dir)
        self._startup_grace = float(startup_grace)
        self._dedup = DedupCache(max_size=100)
        # topic -> set of StreamWriter subscribers (managed by wire.py)
        self._subs: Dict[str, Set[asyncio.StreamWriter]] = {}

    def start(self) -> None:
        """Start node services (consensus, API, replication)."""
        try:
            asyncio.run(self._start_async())
        except KeyboardInterrupt:
            print(f"\nNode {self.node_id} shutting down...")

    async def _start_async(self) -> None:
        try:
            # Initialize Raft consensus
            self._raft = Raft(self.node_id, self.other_nodes)
            # Add a startup grace so peers have time to bring up RPC
            self._raft.set_startup_grace(self._startup_grace)
            # Provide API address hint to Raft for redirects
            self._raft.api_host = self.host
            self._raft.api_port = self.port
            
            # Provide RPC client factory to Raft
            self._raft.rpc_client_factory = lambda host, port, node_id: RpcClient(host, port, node_id)
            # Wire apply callback to durability (CommitLog)
            self._raft.set_apply_callback(self._apply_payload)

            
            # Start API server (for clients)
            self._api_server = await create_api_server(self.host, self.port, node=self)
            
            # Start RPC server (for other nodes) on port + 1000
            rpc_port = self.port + 1000
            self._rpc_server = RpcServer(self.host, rpc_port, self.node_id, self._raft, node=self)
            await self._rpc_server.start()
            # Mark RPC as ready (starts the grace countdown)
            self._raft.mark_rpc_ready()
            
            print(f"Node {self.node_id} started:")
            print(f"  API server: {self.host}:{self.port} (PING -> PONG)")
            print(f"  RPC server: {self.host}:{rpc_port} (inter-node communication)")
            print(f"  Raft state: {self._raft.state.value} (term {self._raft.current_term})")
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

    # Apply committed payloads to durable commit log
    def _apply_payload(self, payload: dict) -> None:
        try:
            topic = payload.get("topic")
            mid = payload.get("id")
            ts = payload.get("ts")
            msg = payload.get("msg")
            if not (topic and mid is not None and ts is not None and msg is not None):
                return
            rec = self._log.append(topic, mid, float(ts), str(msg))
            # Fan-out to live subscribers for this topic
            try:
                asyncio.get_event_loop().create_task(
                    self._broadcast_applied(topic, rec)
                )
            except RuntimeError:
                # No running loop (e.g., during teardown); skip broadcast
                pass
        except Exception:
            # Ignore apply failures here; production code should log
            pass

    def _add_subscriber(self, topic: str, writer: asyncio.StreamWriter) -> None:
        self._subs.setdefault(topic, set()).add(writer)

    def _remove_writer(self, writer: asyncio.StreamWriter) -> None:
        for subs in self._subs.values():
            subs.discard(writer)

    async def _broadcast_applied(self, topic: str, rec: dict) -> None:
        line = (
            f"MSG {topic} {rec.get('id','')} {rec.get('offset',0)} {rec.get('ts')} {rec.get('msg','')}\n"
        )
        dead: Set[asyncio.StreamWriter] = set()
        for w in list(self._subs.get(topic, set())):
            try:
                w.write(line.encode("utf-8"))
                await w.drain()
            except Exception:
                dead.add(w)
        for w in dead:
            self._remove_writer(w)
