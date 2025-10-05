"""Text-based wire protocol for clients (minimal PING server).

Supported commands (so far):
- PING -> PONG

Future commands:
- SUB <topic>
- PUB <topic> <message...>
- HISTORY <topic> <n>
"""

from __future__ import annotations

import asyncio


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        data = await reader.readline()
        line = data.decode("utf-8").strip()

        if line.upper() == "PING":
            writer.write(b"PONG\n")
        else:
            writer.write(b"ERR unknown\n")
        await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def create_api_server(host: str, port: int) -> asyncio.AbstractServer:
    """Create the API server (does not block). Useful for tests."""
    server = await asyncio.start_server(_handle_client, host, port)
    return server


async def _serve_forever(host: str, port: int) -> None:
    server = await create_api_server(host, port)
    async with server:
        await server.serve_forever()


def start_api_server(host: str, port: int) -> None:
    """Start client API server and block forever."""
    asyncio.run(_serve_forever(host, port))

