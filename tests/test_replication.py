import time
import tempfile
from pathlib import Path

from src.replication.log import CommitLog
from src.replication.dedup import DedupCache


def test_offsets_monotonic_per_topic():
    with tempfile.TemporaryDirectory() as td:
        log = CommitLog(base_dir=td)
        t = "chat"
        r1 = log.append(t, "id1", time.time(), "m1")
        r2 = log.append(t, "id2", time.time(), "m2")
        r3 = log.append(t, "id3", time.time(), "m3")
        assert [r1["offset"], r2["offset"], r3["offset"]] == [1, 2, 3]


def test_idempotent_append_with_dedup():
    with tempfile.TemporaryDirectory() as td:
        log = CommitLog(base_dir=td)
        cache = DedupCache(max_size=100)
        t = "chat"
        mid = "same-id"
        # First time should append
        if not cache.seen(t, mid):
            log.append(t, mid, time.time(), "hello")
        # Duplicate should not append
        if not cache.seen(t, mid):
            log.append(t, mid, time.time(), "hello")
        # Verify only one record persisted
        last = log.read_last(t, 10)
        assert len(last) == 1
        assert last[0]["id"] == mid


def test_read_last_returns_in_order():
    with tempfile.TemporaryDirectory() as td:
        log = CommitLog(base_dir=td)
        t = "chat"
        for i in range(1, 6):
            log.append(t, f"id{i}", time.time(), f"m{i}")
        last2 = log.read_last(t, 2)
        assert [r["offset"] for r in last2] == [4, 5]


def test_persistence_across_reopen():
    with tempfile.TemporaryDirectory() as td:
        t = "chat"
        log = CommitLog(base_dir=td)
        for i in range(1, 4):
            log.append(t, f"id{i}", time.time(), f"m{i}")
        # Re-open new instance on same dir
        log2 = CommitLog(base_dir=td)
        r4 = log2.append(t, "id4", time.time(), "m4")
        assert r4["offset"] == 4
        all4 = log2.read_last(t, 10)
        assert len(all4) == 4


def test_dedup_lru_capacity():
    cache = DedupCache(max_size=100)
    t = "chat"
    # Fill 100 unique IDs
    for i in range(100):
        assert cache.seen(t, f"id{i}") is False
    # Access a few to move them to MRU
    for i in range(95, 100):
        assert cache.seen(t, f"id{i}") is True
    # Add a new one, should evict the oldest (id0)
    assert cache.seen(t, "id_new") is False
    # id0 should have been evicted by LRU policy
    assert cache.seen(t, "id0") is False

