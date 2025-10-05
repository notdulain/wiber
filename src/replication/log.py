"""Append-only commit log per topic (skeleton)."""


class CommitLog:
    def append(self, topic: str, record: dict) -> None:
        pass

    def read_last(self, topic: str, n: int) -> list:
        return []

