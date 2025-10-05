"""Lamport clock utility (skeleton)."""


class LamportClock:
    def __init__(self, initial: int = 0):
        self.t = initial

    def tick(self) -> int:
        self.t += 1
        return self.t

    def update(self, received: int) -> int:
        self.t = max(self.t, received) + 1
        return self.t

