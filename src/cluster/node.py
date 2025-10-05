"""Node process entry and orchestration (skeleton).

Responsibilities:
- Initialize consensus (Raft) and RPC server
- Start client-facing API (wire protocol)
- Manage replication log and dedup cache
"""

from __future__ import annotations

import asyncio
from typing import Optional

from api.wire import create_api_server


class Node:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None

    def start(self) -> None:
        """Start node services (consensus, API, replication)."""
        try:
            asyncio.run(self._start_async())
        except KeyboardInterrupt:
            print(f"\nNode {self.node_id} shutting down...")

    async def _start_async(self) -> None:
        # For Task 0.3: only start the API server
        self._server = await create_api_server(self.host, self.port)
        print(f"Node {self.node_id} API server running on {self.host}:{self.port}")
        print("Press Ctrl+C to stop")
        async with self._server:
            await self._server.serve_forever()

