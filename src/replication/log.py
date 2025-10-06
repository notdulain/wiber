"""Append-only JSONL commit log per topic.

Features (Phase 0):
- Per-topic files under a base directory (default: .data)
- Monotonic, 1-based offsets per topic
- Durable appends (flush + fsync)
- Read last N committed records in order

Idempotency is handled by a separate DedupCache; CommitLog does not deduplicate.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List


class CommitLog:
    def __init__(self, base_dir: str | os.PathLike = ".data") -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._next_offset: Dict[str, int] = {}

    def _topic_path(self, topic: str) -> Path:
        return self.base_path / f"{topic}.log"

    def _load_next_offset(self, topic: str) -> int:
        path = self._topic_path(topic)
        if not path.exists():
            self._next_offset[topic] = 1
            return 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Count lines to derive next offset (1-based)
                count = sum(1 for _ in f)
        except FileNotFoundError:
            count = 0
        next_off = count + 1 if count >= 0 else 1
        self._next_offset[topic] = next_off
        return next_off

    def next_offset(self, topic: str) -> int:
        if topic not in self._next_offset:
            return self._load_next_offset(topic)
        return self._next_offset[topic]

    def append(
        self,
        topic: str,
        message_id: str,
        ts: float,
        msg: str,
        *,
        corrected_ts: float | None = None,
        logical_time: int | None = None,
        clock_type: str | None = None,
    ) -> Dict:
        """Append a record and return it with assigned offset.

        Record schema: {"id", "offset", "ts", "msg"}
        """
        offset = self.next_offset(topic)
        record = {"id": message_id, "offset": offset, "ts": ts, "msg": msg}
        if corrected_ts is not None:
            record["corrected_ts"] = corrected_ts
        if logical_time is not None:
            record["logical_time"] = logical_time
        if clock_type:
            record["clock_type"] = clock_type
        path = self._topic_path(topic)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # On some platforms fsync may not be supported; ignore.
                pass
        # Increment next offset for the topic
        self._next_offset[topic] = offset + 1
        return record

    def read_last(self, topic: str, n: int) -> List[Dict]:
        path = self._topic_path(topic)
        if not path.exists() or n <= 0:
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        out: List[Dict] = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
