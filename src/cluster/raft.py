"""Raft consensus (skeleton).

Include:
- Persistent state: currentTerm, votedFor, log
- Volatile state: commitIndex, lastApplied
- RPCs: RequestVote, AppendEntries
"""


class Raft:
    def __init__(self, node_id: str):
        self.node_id = node_id

    def tick(self) -> None:
        """Advance timers and handle elections/heartbeats (placeholder)."""
        pass

