import asyncio
import time
import sys
from pathlib import Path
import contextlib

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pytest

from cluster.node import Node  # noqa: E402
from cluster.rpc import RpcClient  # noqa: E402


@pytest.mark.asyncio
async def test_phase3_replication_end_to_end(unused_tcp_port_factory, tmp_path):
    host = "127.0.0.1"
    p1 = unused_tcp_port_factory()
    p2 = unused_tcp_port_factory()
    p3 = unused_tcp_port_factory()

    # Disable startup grace in tests to speed up elections
    n1 = Node("n1", host=host, port=p1, other_nodes=[(host, p2), (host, p3)], data_dir=str(tmp_path), startup_grace=0.0)
    n2 = Node("n2", host=host, port=p2, other_nodes=[(host, p1), (host, p3)], data_dir=str(tmp_path), startup_grace=0.0)
    n3 = Node("n3", host=host, port=p3, other_nodes=[(host, p1), (host, p2)], data_dir=str(tmp_path), startup_grace=0.0)

    tasks = [
        asyncio.create_task(n1._start_async()),
        asyncio.create_task(n2._start_async()),
        asyncio.create_task(n3._start_async()),
    ]

    try:
        # wait until RPC servers are up
        for node in (n1, n2, n3):
            for _ in range(200):
                if node._raft and node._rpc_server and getattr(node._rpc_server, "_server", None):
                    break
                await asyncio.sleep(0.01)

        # Force n1 to start an election to speed up convergence
        if n1._raft:
            n1._raft._start_election()

        # wait for election
        leader = None
        for _ in range(200):
            for n in (n1, n2, n3):
                if n._raft and n._raft.state.value == "leader":
                    leader = n
                    break
            if leader:
                break
            await asyncio.sleep(0.05)
        assert leader is not None, "no leader elected"

        # append two entries via RPC to the leader
        client = RpcClient(leader.host, leader.port + 1000, "tester")
        for i in range(2):
            payload = {"topic": "it", "id": f"id{i}", "ts": time.time(), "msg": f"m{i}"}
            resp = await client.leader_append(payload)
            assert resp.get("status") == "ok"

        # allow time to replicate and commit
        for _ in range(200):
            if all(n._raft.commit_index >= 2 for n in (n1, n2, n3)):
                break
            await asyncio.sleep(0.05)
        assert n1._raft.commit_index >= 2
        assert n2._raft.commit_index >= 2
        assert n3._raft.commit_index >= 2

        # logs persisted in tmp_path
        log_path = tmp_path / "it.log"
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
    finally:
        for t in tasks:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t
