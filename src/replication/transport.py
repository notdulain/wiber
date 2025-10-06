"""Leader-side replication helpers built on Raft AppendEntries.

These helpers provide convenient wrappers to send AppendEntries to peers for
either fire-and-forget propagation or quorum-based commit decisions.

Note: In proper Raft, commitIndex is advanced by counting successful
AppendEntries responses (matchIndex) per follower and applying majority rules.
Here we expose a simple quorum helper to be adapted to the Raft state.
"""

from __future__ import annotations

import asyncio
from typing import Iterable, Tuple, List, Dict, Any

from cluster.rpc import RpcClient


async def replicate_fire_and_forget(
    leader_id: str,
    peers: Iterable[Tuple[str, int]],
    term: int,
    prev_log_index: int,
    prev_log_term: int,
    entries: List[Dict[str, Any]],
    leader_commit: int,
) -> None:
    """Send AppendEntries to peers without waiting for quorum.

    Silently ignores send errors; intended for best-effort propagation when
    higher-level logic (Raft) will retry as needed.
    """
    tasks = []
    for host, port in peers:
        client = RpcClient(host, port + 1000, leader_id)
        tasks.append(
            client.append_entries(
                leader_id=leader_id,
                term=term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries,
                leader_commit=leader_commit,
            )
        )
    await asyncio.gather(*tasks, return_exceptions=True)


async def replicate_with_quorum(
    leader_id: str,
    peers: Iterable[Tuple[str, int]],
    term: int,
    prev_log_index: int,
    prev_log_term: int,
    entries: List[Dict[str, Any]],
    leader_commit: int,
    quorum: int,
) -> bool:
    """Send AppendEntries to all peers and return True when quorum is met.

    Local append is assumed to be done already and counts as one ACK; the
    returned boolean indicates if enough followers responded success=True to
    reach the quorum value.
    """
    acks = 1  # local append counts as one
    tasks = []
    for host, port in peers:
        client = RpcClient(host, port + 1000, leader_id)
        tasks.append(
            client.append_entries(
                leader_id=leader_id,
                term=term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries,
                leader_commit=leader_commit,
            )
        )
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, dict) and r.get("method") == "append_entries_response" and r.get("success"):
            acks += 1
            if acks >= quorum:
                return True
    return False

