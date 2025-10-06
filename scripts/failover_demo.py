#!/usr/bin/env python3
"""Interactive failover demonstration script.

Starts three nodes in-process, publishes a message, kills the current leader,
verifies a new leader is elected, publishes again, and restarts the old leader.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

# Ensure repo root and src/ are on sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.cluster.node import Node


async def send_command(host: str, port: int, command: str) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write((command + "\n").encode())
    await writer.drain()
    resp = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return resp.decode().strip()


async def publish(host: str, port: int, topic: str, message: str) -> str:
    return await send_command(host, port, f"PUB {topic} {message}")


async def history(host: str, port: int, topic: str, n: int = 5) -> List[str]:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"HISTORY {topic} {n}\n".encode())
    await writer.drain()
    lines = []
    while True:
        line = await reader.readline()
        if not line:
            break
        decoded = line.decode().strip()
        lines.append(decoded)
        if decoded == "OK history_end":
            break
    writer.close()
    await writer.wait_closed()
    return lines


async def wait_for_leader(nodes: List[Node], retries: int = 200) -> Node | None:
    for _ in range(retries):
        for node in nodes:
            if node and node._raft and node._raft.state.value == "leader":
                return node
        await asyncio.sleep(0.1)
    return None


async def main() -> None:
    layout: List[Tuple[str, int]] = [("n1", 9101), ("n2", 9102), ("n3", 9103)]
    nodes: List[Node | None] = []
    tasks: List[asyncio.Task] = []

    print("Starting nodes...")
    for node_id, port in layout:
        others = [(host, p) for host, p in layout if p != port]
        node = Node(
            node_id,
            host="127.0.0.1",
            port=port,
            other_nodes=others,
            data_dir=f"data/failover/{node_id}",
            startup_grace=0.0,
        )
        nodes.append(node)
        task = asyncio.create_task(node._start_async())
        tasks.append(task)
        await asyncio.sleep(0.5)

    leader = await wait_for_leader([n for n in nodes if n])
    if not leader:
        print("Failed to elect initial leader")
        return
    print(f"Initial leader: {leader.node_id}")

    input("Press Enter to publish a message before failover...")
    resp = await publish(leader.host, leader.port, "demo", "before-failover")
    print("Publish response:", resp)

    # Kill leader
    leader_index = nodes.index(leader)
    print(f"Cancelling leader {leader.node_id}...")
    tasks[leader_index].cancel()
    try:
        await tasks[leader_index]
    except asyncio.CancelledError:
        pass
    nodes[leader_index] = None

    new_leader = await wait_for_leader([n for n in nodes if n])
    if not new_leader:
        print("No leader elected after failover")
        return
    print(f"New leader after failover: {new_leader.node_id}")

    input("Press Enter to publish a message after failover...")
    resp = await publish(new_leader.host, new_leader.port, "demo", "after-failover")
    print("Publish response:", resp)

    # Restart old leader
    old_id, old_port = layout[leader_index]
    print(f"Restarting {old_id}...")
    restart = Node(
        old_id,
        host="127.0.0.1",
        port=old_port,
        other_nodes=[(host, p) for host, p in layout if p != old_port],
        data_dir=f"data/failover/{old_id}",
        startup_grace=0.0,
    )
    nodes[leader_index] = restart
    tasks[leader_index] = asyncio.create_task(restart._start_async())

    await asyncio.sleep(2)
    print("History on restarted node:")
    hist = await history(restart.host, restart.port, "demo", 10)
    for line in hist:
        print("  ", line)

    input("Press Enter to shut down nodes...")
    for task in tasks:
        if not task:
            continue
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    print("Failover demo complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
