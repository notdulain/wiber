"""Node process entry and orchestration.

Responsibilities:
- Initialize consensus (Raft) and RPC server
- Start client-facing API (wire protocol)
- Manage replication log and dedup cache
"""

from __future__ import annotations

import asyncio
from typing import Optional

from api.wire import create_api_server
from cluster.rpc import RpcServer, RpcClient


class Node:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._api_server: Optional[asyncio.AbstractServer] = None
        self._rpc_server: Optional[RpcServer] = None

    def start(self) -> None:
        """Start node services (consensus, API, replication)."""
        try:
            asyncio.run(self._start_async())
        except KeyboardInterrupt:
            print(f"\nNode {self.node_id} shutting down...")

    async def _start_async(self) -> None:
        # Start API server (for clients)
        self._api_server = await create_api_server(self.host, self.port)
        
        # Start RPC server (for other nodes) on port + 1000
        rpc_port = self.port + 1000
        self._rpc_server = RpcServer(self.host, rpc_port, self.node_id)
        await self._rpc_server.start()
        
        print(f"Node {self.node_id} started:")
        print(f"  API server: {self.host}:{self.port} (PING -> PONG)")
        print(f"  RPC server: {self.host}:{rpc_port} (inter-node communication)")
        print("Press Ctrl+C to stop")
        
        # Run both servers concurrently
        async with self._api_server:
            await asyncio.gather(
                self._api_server.serve_forever(),
                self._keep_alive()
            )

    async def _keep_alive(self) -> None:
        """Keep the node running (placeholder for future heartbeat logic)."""
        while True:
            await asyncio.sleep(1)

    async def ping_other_node(self, other_host: str, other_port: int) -> dict:
        """Ping another node via RPC."""
        rpc_port = other_port + 1000  # RPC is on port + 1000
        client = RpcClient(other_host, rpc_port, self.node_id)
        return await client.ping()

