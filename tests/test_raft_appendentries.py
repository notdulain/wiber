"""Follower AppendEntries consistency tests."""

import sys
from pathlib import Path

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cluster.raft import Raft, RaftState, LogEntry  # noqa: E402


def test_prev_index_too_large_rejects():
    r = Raft("n2")
    r.current_term = 1
    # follower has empty log
    resp = r.handle_append_entries("n1", term=1, prev_log_index=1, prev_log_term=1, entries=[], leader_commit=0)
    assert resp["success"] is False
    assert resp["term"] == 1


def test_append_new_entries_on_empty_log():
    r = Raft("n2")
    r.current_term = 1
    entries = [
        {"term": 1, "payload": {"msg": "a"}},
        {"term": 1, "payload": {"msg": "b"}},
    ]
    resp = r.handle_append_entries("n1", term=1, prev_log_index=0, prev_log_term=0, entries=entries, leader_commit=1)
    assert resp["success"] is True
    assert len(r.log) == 2
    assert r.log[0].index == 1 and r.log[0].term == 1
    assert r.log[1].index == 2 and r.log[1].payload["msg"] == "b"
    assert r.commit_index == 1


def test_conflict_resolution_truncates_and_appends():
    r = Raft("n2")
    r.current_term = 2
    # existing log: [ (1,term1), (2,term1) ]
    r.log = [LogEntry(1, 1, {}), LogEntry(2, 1, {})]
    # leader sends prev=1,term=1 and entry at index 2 with term 2
    entries = [
        {"term": 2, "payload": {"msg": "new2"}},
    ]
    resp = r.handle_append_entries("n1", term=2, prev_log_index=1, prev_log_term=1, entries=entries, leader_commit=2)
    assert resp["success"] is True
    assert len(r.log) == 2
    assert r.log[0].term == 1
    assert r.log[1].term == 2 and r.log[1].payload["msg"] == "new2"
    assert r.commit_index == 2

