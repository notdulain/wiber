#!/usr/bin/env python3
"""FastAPI gateway that exposes Web/HTTP endpoints for direct messaging."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT_DIR / "public" / "index.html"


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines from .env into os.environ if not set."""
    try:
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        # Non-fatal; ignore malformed .env
        pass


# Load .env early so IDE runs pick up settings
_load_dotenv(ROOT_DIR / ".env")

# Configuration
BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "9101"))
# Optional: comma-separated list of host:port to try in order
# Example: "127.0.0.1:9101,127.0.0.1:9102,127.0.0.1:9103"
BROKER_NODES = os.getenv("BROKER_NODES")
APP_PORT = int(os.getenv("GATEWAY_PORT", "8080"))

app = FastAPI(title="DM Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DMRequest(BaseModel):
    message: str
    sender: str | None = None
    message_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    if INDEX_PATH.exists():
        return HTMLResponse(INDEX_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>DM Gateway</h1><p>UI not found. Place index.html under public/.</p>")


def _candidate_brokers() -> list[tuple[str, int]]:
    # Order: explicit BROKER_NODES if set, else BROKER_HOST:PORT only
    nodes: list[tuple[str, int]] = []
    if BROKER_NODES:
        for part in BROKER_NODES.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                h, p = part.rsplit(":", 1)
                try:
                    nodes.append((h.strip(), int(p)))
                except ValueError:
                    continue
    # Always include the primary as a fallback (dedupe later)
    nodes.append((BROKER_HOST, BROKER_PORT))
    # Deduplicate while preserving order
    seen = set()
    ordered: list[tuple[str, int]] = []
    for hp in nodes:
        if hp not in seen:
            ordered.append(hp)
            seen.add(hp)
    return ordered


async def _open_any_broker() -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
    last_err: Exception | None = None
    for host, port in _candidate_brokers():
        try:
            return await asyncio.open_connection(host, port)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    if last_err:
        raise last_err
    return None


async def broker_command(command: str) -> List[str]:
    reader, writer = await _open_any_broker()
    try:
        writer.write((command + "\n").encode("utf-8"))
        await writer.drain()
        lines: List[str] = []
        while True:
            line = await reader.readline()
            if not line:
                break
            decoded = line.decode("utf-8").strip()
            lines.append(decoded)
            if decoded.startswith("OK") or decoded.startswith("ERR"):
                break
    
    finally:
        writer.close()
        await writer.wait_closed()
    return lines


def parse_message(line: str) -> Dict[str, Any]:
    parts = line.split(maxsplit=7)
    if len(parts) < 8:
        raise ValueError(f"Unexpected broker line: {line}")
    kind, topic, msg_id, offset, ts, corrected, logical, tail = parts
    clock_type = None
    text = ""
    subparts = tail.split(maxsplit=1)
    if subparts:
        clock_type = subparts[0] if subparts[0] != '-' else None
        if len(subparts) > 1:
            text = subparts[1]
    return {
        "kind": kind,
        "topic": topic,
        "message_id": msg_id,
        "offset": int(offset),
        "timestamp": float(ts),
        "corrected_ts": float(corrected) if corrected not in {"-", ""} else None,
        "logical_time": int(logical) if logical not in {"-", ""} else None,
        "clock_type": clock_type,
        "text": text,
    }


@app.post("/dm/{convo_id}")
async def send_message(convo_id: str, payload: DMRequest) -> Dict[str, Any]:
    text = payload.message.replace("\n", " ").strip()
    if payload.sender:
        text = f"{payload.sender}: {text}"
    message_id = payload.message_id or f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    command = f"PUB {convo_id} --id {message_id} {text}"
    lines = await broker_command(command)
    if not lines:
        raise HTTPException(status_code=500, detail="No response from broker")
    status = lines[-1]
    if status.startswith("ERR"):
        raise HTTPException(status_code=500, detail=status)
    return {
        "status": status,
        "message_id": message_id,
    }


@app.get("/dm/{convo_id}/history")
async def fetch_history(convo_id: str, count: int = 50) -> List[Dict[str, Any]]:
    command = f"HISTORY {convo_id} {count}"
    reader, writer = await _open_any_broker()
    messages: List[Dict[str, Any]] = []
    try:
        writer.write((command + "\n").encode("utf-8"))
        await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("HISTORY "):
                messages.append(parse_message(decoded))
            elif decoded.startswith("OK "):
                break
            elif decoded.startswith("ERR"):
                raise HTTPException(status_code=500, detail=decoded)
    finally:
        writer.close()
        await writer.wait_closed()
    # expand message text for UI convenience
    for msg in messages:
        msg["display"] = f"[{msg['timestamp']:.3f}] {msg['text']}"
    return messages


@app.websocket("/ws/{convo_id}")
async def dm_websocket(websocket: WebSocket, convo_id: str):
    await websocket.accept()
    try:
        reader, writer = await _open_any_broker()
        try:
            writer.write(f"SUB {convo_id}\n".encode("utf-8"))
            await writer.drain()
            await websocket.send_json({"event": "connected"})
            while True:
                line = await reader.readline()
                if not line:
                    await websocket.send_json({"event": "broker_closed"})
                    break
                decoded = line.decode("utf-8").strip()
                if decoded.startswith("MSG "):
                    await websocket.send_json({"event": "message", "payload": parse_message(decoded)})
                elif decoded.startswith("ERR"):
                    await websocket.send_json({"event": "error", "detail": decoded})
        finally:
            writer.close()
            await writer.wait_closed()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        await websocket.close(code=1011, reason=str(exc))


# --- Cluster discovery + node log streaming ---
try:
    # Import cluster config loader for node list
    from src.config.cluster import load_cluster_config  # type: ignore
except Exception:
    load_cluster_config = None  # type: ignore


def _resolve_node_log_path(node_id: str) -> Path | None:
    """Try common locations for a node's structured log file.

    Prefers .data/<id>/logs/console.log (raw stdout/stderr); falls back to
    node.log and other common paths.
    """
    candidates = [
        ROOT_DIR / ".data" / node_id / "logs" / "console.log",
        ROOT_DIR / "data" / node_id / "logs" / "console.log",
        ROOT_DIR / "data" / "failover" / node_id / "logs" / "console.log",
        ROOT_DIR / ".data" / node_id / "logs" / "node.log",
        ROOT_DIR / "data" / node_id / "logs" / "node.log",
        ROOT_DIR / "data" / "failover" / node_id / "logs" / "node.log",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Return preferred path even if missing, so we can wait for creation
    return candidates[0]


@app.get("/cluster/nodes")
async def cluster_nodes() -> List[Dict[str, str | int]]:
    cfg_path = ROOT_DIR / "config" / "cluster.yaml"
    nodes: List[Dict[str, str | int]] = []
    try:
        if load_cluster_config is None:
            raise RuntimeError("cluster loader unavailable")
        cfg = load_cluster_config(str(cfg_path))
        for n in cfg.nodes:
            nodes.append({"id": n.id, "host": n.host, "port": n.port})
    except Exception:
        # Fallback to default demo topology
        nodes = [
            {"id": "n1", "host": "127.0.0.1", "port": 9101},
            {"id": "n2", "host": "127.0.0.1", "port": 9102},
            {"id": "n3", "host": "127.0.0.1", "port": 9103},
        ]
    return nodes


@app.websocket("/ws/node/{node_id}/logs")
async def node_logs(websocket: WebSocket, node_id: str) -> None:
    # Read optional tail count from query (default 200); tail=0 means start empty
    try:
        tail_count = int(websocket.query_params.get("tail", "200"))
    except Exception:
        tail_count = 200
    await websocket.accept()
    path = _resolve_node_log_path(node_id)
    try:
        # Wait for file to exist (if needed) with a timeout loop
        for _ in range(40):  # ~10 seconds total
            if path and path.exists():
                break
            await asyncio.sleep(0.25)
        if not path:
            await websocket.send_json({"event": "error", "detail": "log path unavailable"})
            await websocket.close(code=1011)
            return

        # Open and send a small tail (last 200 lines) then follow
        try:
            f = open(path, "r", encoding="utf-8")
        except FileNotFoundError:
            await websocket.send_json({"event": "info", "detail": "log not found yet"})
            f = None

        if f and tail_count > 0:
            try:
                # Read all lines and keep only last 200
                lines = f.readlines()
                for line in lines[-tail_count:]:
                    await websocket.send_json({"event": "log", "line": line.rstrip("\n")})
            except Exception:
                pass
        # If starting with a clean terminal, jump to EOF so we only stream new lines
        if f and tail_count == 0:
            try:
                import os as _os
                f.seek(0, _os.SEEK_END)
            except Exception:
                pass

        # Follow new lines using non-blocking reads; handle truncation
        pending = ""
        import os as _os
        first_opened = f is not None
        while True:
            if not f:
                try:
                    f = open(path, "r", encoding="utf-8")
                    first_opened = True
                    if tail_count == 0:
                        try:
                            f.seek(0, _os.SEEK_END)
                        except Exception:
                            pass
                except FileNotFoundError:
                    await asyncio.sleep(0.5)
                    continue
            try:
                # Detect truncation (e.g., node restart)
                size = (_os.stat(path).st_size) if path else 0
                pos = f.tell()
                if pos > size:
                    f.seek(0)
                    pending = ""
                data = f.read()
            except Exception:
                data = ""
            if not data:
                await asyncio.sleep(0.2)
                continue
            pending += data
            while True:
                nl = pending.find("\n")
                if nl == -1:
                    break
                line = pending[:nl]
                pending = pending[nl + 1 :]
                await websocket.send_json({"event": "log", "line": line})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.close(code=1011, reason=str(exc))
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=APP_PORT, reload=False)
