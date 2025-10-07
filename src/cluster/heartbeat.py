
"""Leader heartbeats using Raft AppendEntries (empty entries).

- Leader sends AppendEntries with empty `entries` at a fixed interval (50 ms).
- Followers reset their election timers on receipt (handled in Raft handler).
- This module does not manage elections; it only emits heartbeats when called.

Usage (example):
    # schedule alongside node services
    asyncio.create_task(run_raft_heartbeats(node))
"""

from __future__ import annotations

import asyncio
import time
from typing import Iterable, Tuple

from cluster.rpc import RpcClient


DEFAULT_HEARTBEAT_INTERVAL = 0.05  # 50 ms


async def run_raft_heartbeats(
    node,
    interval: float = DEFAULT_HEARTBEAT_INTERVAL,
) -> None:
    """Continuously send empty AppendEntries from leader to all peers.

    Expects `node` to provide:
      - node_id: str
      - other_nodes: Iterable[Tuple[str, int]]  # (host, port)
      - _raft.current_term: int
      - _raft.commit_index: int

    This function is safe to run for all nodes: followers will attempt to send
    but do nothing useful until elected as leader; typically you schedule this
    only for the leader role.
    """
    while True:
        try:
            if getattr(node, "_raft", None) is not None and getattr(node._raft, "state", None):
                # Send only if node is leader; otherwise sleep
                state_val = getattr(node._raft.state, "value", "")
                if state_val == "leader":
                    term = int(getattr(node._raft, "current_term", 0))
                    leader_commit = int(getattr(node._raft, "commit_index", 0))
                    for host, port in list(getattr(node, "other_nodes", [])):
                        try:
                            client = RpcClient(host, port + 1000, node.node_id)
                            # For Phase 2/early Phase 3, send prev indices as 0
                            await client.append_entries(
                                leader_id=node.node_id,
                                term=term,
                                prev_log_index=0,
                                prev_log_term=0,
                                entries=[],
                                leader_commit=leader_commit,
                            )
                        except Exception:
                            # ignore transient send failures
                            pass
        finally:
            await asyncio.sleep(interval)
