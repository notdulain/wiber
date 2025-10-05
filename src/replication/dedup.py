"""Producer message ID deduplication (skeleton)."""


class DedupCache:
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size

    def seen(self, topic: str, message_id: str) -> bool:
        return False

