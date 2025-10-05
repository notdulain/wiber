"""RPC transport for cluster messages using JSON Lines framing.

Includes:
- JsonlCodec: helpers to encode/decode messages for unit tests (no sockets).
- Asyncio-based server/client skeleton (not exercised by unit tests).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict


@dataclass
class RpcMessage:
    type: str
    sender: str
    term: int
    payload: Dict[str, Any]


class JsonlCodec:
    @staticmethod
    def encode(msg: RpcMessage) -> bytes:
        return (json.dumps({
            "type": msg.type,
            "from": msg.sender,
            "term": msg.term,
            "payload": msg.payload,
        }) + "\n").encode("utf-8")

    @staticmethod
    def decode_lines(data: bytes) -> list[RpcMessage]:
        out: list[RpcMessage] = []
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            out.append(RpcMessage(
                type=obj.get("type", ""),
                sender=obj.get("from", ""),
                term=int(obj.get("term", 0)),
                payload=obj.get("payload") or {},
            ))
        return out


class RpcServer:
    def __init__(self, host: str, port: int, handler: Callable[[RpcMessage], None]):
        self.host = host
        self.port = port
        self._handler = handler
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._on_client, self.host, self.port)

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    msgs = JsonlCodec.decode_lines(line)
                    for m in msgs:
                        self._handler(m)
                except Exception:
                    # ignore bad lines in early phases
                    continue
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


class RpcClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    async def send(self, msg: RpcMessage) -> None:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        writer.write(JsonlCodec.encode(msg))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

