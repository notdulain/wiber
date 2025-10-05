"""RPC transport for Raft messages (skeleton).

Use simple TCP/JSON framing between nodes.
"""


class RpcServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def start(self) -> None:
        """Start listening for RPC calls (placeholder)."""
        pass


class RpcClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def call(self, method: str, payload: dict) -> dict:
        """Send RPC request (placeholder)."""
        return {}

