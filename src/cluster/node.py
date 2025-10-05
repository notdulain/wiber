"""Node process entry and orchestration (Phase 1 skeleton).

Responsibilities (Phase 1):
- Load cluster config
- Start RPC server
- If static leader: emit heartbeats periodically
- If follower: record last-seen heartbeat timestamps
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict

from ..cluster.rpc import RpcServer, RpcClient, RpcMessage
from ..config.cluster import load_cluster_config, ClusterConfig


HEARTBEAT_INTERVAL_SEC = 0.5
HEARTBEAT_TIMEOUT_SEC = 1.5


class Node:
    def __init__(self, node_id: str, config_path: str = "config/cluster.yaml"):
        self.node_id = node_id
        self.config: ClusterConfig = load_cluster_config(config_path)
        self.role = "leader" if self.node_id == self.config.leader_id else "follower"
        # Map of peer_id -> last heartbeat ts
        self.last_heartbeat: Dict[str, float] = {}
        # Determine my host/port
        me = next(n for n in self.config.nodes if n.id == self.node_id)
        self.host, self.port = me.host, me.port
        self._server: RpcServer | None = None
        self._hb_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._server = RpcServer(self.host, self.port, handler=self._on_message)
        await self._server.start()
        print(f"node {self.node_id} listening on {self.host}:{self.port} as {self.role}")
        if self.role == "leader":
            self._hb_task = asyncio.create_task(self._heartbeat_loop())
        else:
            self._monitor_task = asyncio.create_task(self._monitor_heartbeats())

    def _on_message(self, msg: RpcMessage) -> None:
        if msg.type == "heartbeat":
            self.last_heartbeat[msg.sender] = time.time()
            if self.role == "follower":
                print(f"{self.node_id} <- hb from {msg.sender} (term={msg.term})")

    async def _heartbeat_loop(self) -> None:
        peers = [n for n in self.config.nodes if n.id != self.node_id]
        while True:
            now = time.time()
            for p in peers:
                try:
                    client = RpcClient(p.host, p.port)
                    await client.send(RpcMessage(type="heartbeat", sender=self.node_id, term=0, payload={"ts": now}))
                    print(f"{self.node_id} -> hb to {p.id}")
                except Exception:
                    # swallow in early phase
                    pass
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)

    async def _monitor_heartbeats(self) -> None:
        while True:
            now = time.time()
            for peer_id, ts in list(self.last_heartbeat.items()):
                if now - ts > HEARTBEAT_TIMEOUT_SEC:
                    # placeholder: in the future, trigger election
                    pass
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC / 2)
