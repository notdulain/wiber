"""Leader-side replication tests (no network; fake RPC client)."""

import sys
from pathlib import Path

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import asyncio
import pytest

from cluster.raft import Raft, RaftState  # noqa: E402


class FakeClient:
    def __init__(self, peer_id: str, behavior: str = "success"):
        self.peer_id = peer_id
        self.behavior = behavior
        self.calls = []

    async def append_entries(self, **kwargs):
        self.calls.append(kwargs)
        if self.behavior == "success":
            return {"method": "append_entries_response", "term": kwargs.get("term", 0), "success": True}
        elif self.behavior == "fail_once":
            # fail first, then succeed
            if getattr(self, "_failed", False):
                return {"method": "append_entries_response", "term": kwargs.get("term", 0), "success": True}
            else:
                self._failed = True
                return {"method": "append_entries_response", "term": kwargs.get("term", 0), "success": False}
        else:
            return {"method": "append_entries_response", "term": kwargs.get("term", 0), "success": False}


def make_factory(mapping):
    def _factory(host, port, node_id):
        key = f"{host}:{port-1000}"  # original peer id used in Raft (host:base_port)
        return mapping[key]
    return _factory


@pytest.mark.asyncio
async def test_majority_commit_advances_and_applies():
    r = Raft("n1", other_nodes=[("h2", 2000), ("h3", 3000)])
    r.state = RaftState.LEADER
    r.current_term = 1
    # init leader indices as on become leader
    r._become_leader()
    applied = []
    r.set_apply_callback(lambda p: applied.append(p))

    # fake clients for peers
    c2 = FakeClient("h2:2000", behavior="success")
    c3 = FakeClient("h3:3000", behavior="success")
    r.rpc_client_factory = make_factory({"h2:2000": c2, "h3:3000": c3})

    # append one entry and replicate
    r.append_local({"msg": "x"})
    await r._replicate_to_peer("h2:2000")
    await r._replicate_to_peer("h3:3000")

    assert r.commit_index == 1
    assert r.last_applied == 1
    assert applied == [{"msg": "x"}]


@pytest.mark.asyncio
async def test_conflict_backoff_then_success():
    r = Raft("n1", other_nodes=[("h2", 2000), ("h3", 3000)])
    r.state = RaftState.LEADER
    r.current_term = 2
    r._become_leader()

    # Prepare log with two entries
    r.append_local({"msg": "a"})  # idx 1
    r.append_local({"msg": "b"})  # idx 2

    # Set next_index for h2 low to force a conflict path
    peer_id = "h2:2000"
    r.next_index[peer_id] = 2  # will send prev_idx=1

    # h2 fails once then succeeds
    c2 = FakeClient(peer_id, behavior="fail_once")
    c3 = FakeClient("h3:3000", behavior="success")
    r.rpc_client_factory = make_factory({peer_id: c2, "h3:3000": c3})

    # First replicate attempts
    await r._replicate_to_peer(peer_id)
    # Should have decremented next_index due to failure
    assert r.next_index[peer_id] == 1

    # Retry now should succeed (fail_once -> success)
    await r._replicate_to_peer(peer_id)
    # After both peers succeed, commit should advance to 2
    await r._replicate_to_peer("h3:3000")

    assert r.commit_index >= 2

