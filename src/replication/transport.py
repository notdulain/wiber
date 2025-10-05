import asyncio
import json
import logging
from urllib.parse import urlparse

REPL_TIMEOUT = 3.0
logger = logging.getLogger(__name__)


def _parse_peer(peer: str) -> tuple[str, int]:
    if "://" in peer:
        u = urlparse(peer)
        host = u.hostname or "127.0.0.1"
        port = u.port or 0
    else:
        host, port_str = peer.split(":", 1)
        host, port = host.strip(), int(port_str)
    return host, int(port)


async def _send_jsonl(host: str, port: int, obj: dict, timeout: float = REPL_TIMEOUT):
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.write((json.dumps(obj) + "\n").encode("utf-8"))
        await writer.drain()
        # Attempt to read an ACK line with small timeout
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=0.5)
            if line:
                return json.loads(line.decode("utf-8"))
        except Exception:
            pass
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        logger.error(f"TCP replication to {host}:{port} failed: {e}")
        return e


async def replicate_to_peers(node, msg):
    """Fire-and-forget replication using raw TCP JSONL.

    Sends a 'replicate' message to alive peers. Marks peers down on errors.
    """
    alive_peers = node.failure_detector.get_alive_peers()
    tasks = []
    for p in alive_peers:
        host, port = _parse_peer(p)
        tasks.append(_send_jsonl(host, port, {"type": "replicate", "msg": msg}))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for p, r in zip(alive_peers, results):
        if isinstance(r, Exception):
            node.failure_detector.peer_status[p]["alive"] = False
            logger.warning(f"Replication to {p} failed, marking as down")


async def replicate_with_quorum(node, msg):
    """Quorum-based replication over raw TCP.

    Leader sends to all alive peers and waits for enough ACKs like {"status":"ok"}.
    Local write counts as one ACK.
    """
    needed = getattr(node, "replication_quorum", 1)
    acks = 1  # local write counts
    alive_peers = node.failure_detector.get_alive_peers()
    tasks = []
    for p in alive_peers:
        host, port = _parse_peer(p)
        tasks.append(_send_jsonl(host, port, {"type": "replicate", "msg": msg}))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, dict) and r.get("status") == "ok":
            acks += 1
            if acks >= needed:
                logger.info(f"Replication quorum achieved: {acks}/{needed}")
                return True

    logger.warning(f"Replication quorum NOT achieved: {acks}/{needed}")
    return False
