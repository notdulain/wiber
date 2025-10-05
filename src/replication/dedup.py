"""Producer message ID deduplication with per-topic LRU cache.

Semantics:
- seen(topic, id) -> bool
  - Returns True if the (topic, id) has been observed before.
  - Returns False and records the id if not seen; may evict LRU to respect capacity.

Capacity applies per-topic (default: 100 entries).
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict


class DedupCache:
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._topics: Dict[str, OrderedDict[str, None]] = {}

    def _cache(self, topic: str) -> OrderedDict:
        if topic not in self._topics:
            self._topics[topic] = OrderedDict()
        return self._topics[topic]

    def seen(self, topic: str, message_id: str) -> bool:
        cache = self._cache(topic)
        if message_id in cache:
            # Move to most-recent position
            cache.move_to_end(message_id)
            return True
        # Not seen; record and enforce capacity
        cache[message_id] = None
        cache.move_to_end(message_id)
        while len(cache) > self.max_size:
            cache.popitem(last=False)  # Evict LRU
        return False

