import asyncio
import json
import logging
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Phase 1 settings: leader-only heartbeats, 1s interval, 3s timeout
DEFAULT_HEARTBEAT_INTERVAL = 0.05  # 50 ms


def _parse_peer(peer: str) -> tuple[str, int]:
    """Accepts 'host:port' or URL like 'http://host:port' and returns (host, port)."""
    if "://" in peer:
        u = urlparse(peer)
        host = u.hostname or "127.0.0.1"
        port = u.port or 0
    else:
        host, port_str = peer.split(":", 1)
        host, port = host.strip(), int(port_str)
    return host, int(port)


async def _send_jsonl(host: str, port: int, obj: dict, timeout: float) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        line = json.dumps(obj) + "\n"
        writer.write(line.encode("utf-8"))
        await writer.drain()
        # Optional: try to read a line (ignore errors/timeouts)
        try:
            await asyncio.wait_for(reader.readline(), timeout=0.2)
        except Exception:
            pass
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def heartbeat_task(app):
    """Leader-only heartbeat loop over raw TCP/JSONL.

    Expects app['node'] to have:
      - id or node_id
      - role ("leader" or "follower")
      - peers: iterable of peer address strings ('host:port' or URLs)
      - failure_detector: FailureDetector
    """
    node = app["node"]
    # Only leader sends heartbeats
    role = getattr(node, "role", None) or getattr(node, "is_leader", False)
    while True:
        now = time.time()
        if role == "leader" or role is True:
            for p in getattr(node, "peers", []):
                host, port = _parse_peer(p)
                ok = await _send_jsonl(host, port, {
                    "type": "heartbeat",
                    "from": getattr(node, "id", None) or getattr(node, "node_id", "unknown"),
                    "term": 0,
                    "payload": {"ts": now},
                }, timeout=HEARTBEAT_INTERVAL)
                if ok:
                    # Mark peer alive when send succeeds (receiver may also echo)
                    node.failure_detector.mark_alive(p, now)
        # Followers do not send heartbeats (Raft semantics)

        # Check for failures periodically (applies to both roles)
        node.failure_detector.heartbeat_timeout = HEARTBEAT_TIMEOUT
        failed_peers = node.failure_detector.check_failures(now)
        for peer in failed_peers:
            logger.warning(f"Node {peer} marked as failed - timeout exceeded")

        await asyncio.sleep(HEARTBEAT_INTERVAL)


# Note: rejoin_sync() is intentionally omitted in this TCP-based design.
