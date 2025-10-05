import asyncio
import sys
from pathlib import Path


# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


import pytest

from api.wire import create_api_server  # noqa: E402


@pytest.mark.asyncio
async def test_ping_responds_pong(unused_tcp_port):
    host = "127.0.0.1"
    port = unused_tcp_port

    server = await create_api_server(host, port)
    async with server:
        # Connect to the server
        reader, writer = await asyncio.open_connection(host, port)
        # Send PING and read response
        writer.write(b"PING\n")
        await writer.drain()
        resp = await reader.readline()
        writer.close()
        await writer.wait_closed()

        assert resp == b"PONG\n"


