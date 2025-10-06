"""Tests for Raft leader local append (Phase 3 hook)."""

import sys
from pathlib import Path

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pytest

from cluster.raft import Raft, RaftState  # noqa: E402


def test_leader_append_creates_sequential_entries():
    r = Raft("n1")
    r.state = RaftState.LEADER
    r.current_term = 1
    e1 = r.append_local({"msg": "a"})
    e2 = r.append_local({"msg": "b"})
    assert e1.index == 1 and e1.term == 1 and e1.payload["msg"] == "a"
    assert e2.index == 2 and e2.term == 1 and e2.payload["msg"] == "b"
    assert r.last_log_index() == 2


def test_append_local_raises_when_not_leader():
    r = Raft("n1")
    r.current_term = 1
    with pytest.raises(RuntimeError):
        r.append_local({"msg": "x"})

