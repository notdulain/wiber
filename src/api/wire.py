"""Text-based wire protocol for clients (PING, PUB, HISTORY).

Supported commands (so far):
- PING -> PONG

Future commands:
- SUB <topic>
- PUB <topic> <message...>
- HISTORY <topic> <n>
"""

from __future__ import annotations

import asyncio
import time
import uuid


async def _handle_pub(line: str, node) -> bytes:
    if node is None or getattr(node, "_raft", None) is None:
        return b"ERR unavailable\n"
    # Require leader
    if getattr(node._raft.state, "value", "") != "leader":
        # Try to redirect if we have a leader hint
        hint = getattr(node, "_leader_hint", None)
        if hint:
            host, port = hint
            return f"REDIRECT {host} {port}\n".encode()
        return b"ERR not_leader\n"
    # Accept: PUB <topic> <message...>  or  PUB <topic> <id> <message...>
    parts3 = line.split(maxsplit=2)
    if len(parts3) < 3:
        return b"ERR usage: PUB <topic> <message>\n"
    topic = parts3[1]
    provided_id = None
    parts4 = line.split(maxsplit=3)
    if len(parts4) == 4 and parts4[0] == "PUB":
        maybe_id = parts4[2].strip()
        if 1 <= len(maybe_id) <= 128:
            provided_id = maybe_id
            message = parts4[3]
        else:
            message = parts3[2]
    else:
        message = parts3[2]

    msg_id = provided_id or f"msg_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
    # Dedup per-topic based on message id (only effective if client reuses id)
    try:
        if getattr(node, "_dedup", None) is not None and node._dedup.seen(topic, msg_id):
            return f"OK duplicate {msg_id}\n".encode()
    except Exception:
        pass

    payload = {
        "topic": topic,
        "id": msg_id,
        "ts": time.time(),
        "msg": message,
    }
    try:
        entry = node._raft.append_local(payload)
    except Exception as e:
        return f"ERR {type(e).__name__}: {e}\n".encode()
    # Wait for commit (simple poll with timeout)
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if node._raft.commit_index >= entry.index:
            return f"OK published {payload['id']}\n".encode()
        await asyncio.sleep(0.01)
    return b"ERR timeout_waiting_commit\n"


async def _handle_history(line: str, node) -> bytes:
    if node is None or getattr(node, "_log", None) is None:
        return b"ERR unavailable\n"
    parts = line.split(maxsplit=2)
    if len(parts) != 3:
        return b"ERR usage: HISTORY <topic> <n>\n"
    topic, n_str = parts[1], parts[2]
    try:
        n = int(n_str)
    except ValueError:
        return b"ERR n_must_be_int\n"
    recs = node._log.read_last(topic, n)
    out = []
    for r in recs:
        out.append(
            f"HISTORY {topic} {r.get('id','')} {r.get('offset',0)} {r.get('ts')} {r.get('msg','')}\n"
        )
    out.append("OK history_end\n")
    return ("".join(out)).encode()


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, node=None) -> None:
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            line = data.decode("utf-8").strip()

            if line.upper() == "PING":
                writer.write(b"PONG\n")
                await writer.drain()
            elif line.startswith("PUB "):
                writer.write(await _handle_pub(line, node))
                await writer.drain()
            elif line.startswith("HISTORY "):
                writer.write(await _handle_history(line, node))
                await writer.drain()
            elif line.startswith("SUB "):
                # Subscribe to a topic and keep the connection open for live messages
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    writer.write(b"ERR usage: SUB <topic>\n")
                    await writer.drain()
                    continue
                topic = parts[1].strip()
                if node is None or not hasattr(node, "_add_subscriber"):
                    writer.write(b"ERR unavailable\n")
                    await writer.drain()
                    continue
                # Register subscriber
                try:
                    node._add_subscriber(topic, writer)
                except Exception:
                    writer.write(b"ERR subscribe_failed\n")
                    await writer.drain()
                    continue
                writer.write(f"OK subscribed {topic}\n".encode())
                await writer.drain()
                # Stay in the loop; any further lines can be QUIT to unsubscribe
            elif line.upper() == "QUIT":
                writer.write(b"OK bye\n")
                await writer.drain()
                break
            else:
                writer.write(b"ERR unknown\n")
                await writer.drain()
    finally:
        try:
            # Remove writer from any subscription lists
            if node is not None and hasattr(node, "_remove_writer"):
                try:
                    node._remove_writer(writer)
                except Exception:
                    pass
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def create_api_server(host: str, port: int, node=None) -> asyncio.AbstractServer:
    """Create the API server (does not block). Useful for tests."""
    server = await asyncio.start_server(lambda r, w: _handle_client(r, w, node=node), host, port)
    return server


async def _serve_forever(host: str, port: int, node=None) -> None:
    server = await create_api_server(host, port, node=node)
    async with server:
        await server.serve_forever()


def start_api_server(host: str, port: int, node=None) -> None:
    """Start client API server and block forever."""
    asyncio.run(_serve_forever(host, port, node=node))
