#!/usr/bin/env python3
"""FastAPI gateway that exposes Web/HTTP endpoints for direct messaging."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from asyncio.subprocess import Process

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT_DIR / "public" / "index.html"

SRC_DIR = ROOT_DIR / "src"
for _path in (ROOT_DIR, SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


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
APP_PORT = int(os.getenv("GATEWAY_PORT", "8081"))

RUN_NODE_SCRIPT = ROOT_DIR / "scripts" / "run_node.py"
CLUSTER_CONFIG_PATH = ROOT_DIR / "config" / "cluster.yaml"
DATA_ROOT = Path(os.getenv("NODE_DATA_ROOT", ROOT_DIR / ".data")).resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

NODE_PROCS: dict[str, Process] = {}
NODE_LOCK = asyncio.Lock()

DEFAULT_CLUSTER = [
    {"id": "n1", "host": "127.0.0.1", "port": 9101},
    {"id": "n2", "host": "127.0.0.1", "port": 9102},
    {"id": "n3", "host": "127.0.0.1", "port": 9103},
]

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


def _load_cluster_nodes(strict: bool = False) -> List[Dict[str, str | int]]:
    if load_cluster_config is None:
        if strict:
            raise RuntimeError("cluster loader unavailable")
        return list(DEFAULT_CLUSTER)
    try:
        cfg = load_cluster_config(str(CLUSTER_CONFIG_PATH))
    except Exception as exc:
        if strict:
            raise exc
        return list(DEFAULT_CLUSTER)
    nodes: List[Dict[str, str | int]] = []
    for n in cfg.nodes:
        nodes.append({"id": n.id, "host": n.host, "port": n.port})
    return nodes


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
    nodes = _load_cluster_nodes(strict=False)
    async with NODE_LOCK:
        running_map = {node_id: _proc_is_running(proc) for node_id, proc in NODE_PROCS.items()}
    seen: set[str] = set()
    for node in nodes:
        node_id = str(node.get("id"))
        seen.add(node_id)
        node["running"] = running_map.get(node_id, False)
    for node_id, running in running_map.items():
        if node_id not in seen:
            nodes.append({"id": node_id, "host": "127.0.0.1", "port": None, "running": running})
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


def _node_ids() -> set[str]:
    ids = {n["id"] for n in _load_cluster_nodes(strict=False)}
    ids.update(NODE_PROCS.keys())
    return ids


def _proc_is_running(proc: Process | None) -> bool:
    return proc is not None and proc.returncode is None


async def _monitor_proc(node_id: str, proc: Process) -> None:
    try:
        await proc.wait()
    finally:
        async with NODE_LOCK:
            existing = NODE_PROCS.get(node_id)
            if existing is proc:
                NODE_PROCS.pop(node_id, None)


async def _start_node(node_id: str) -> bool:
    if not RUN_NODE_SCRIPT.exists():
        raise RuntimeError(f"run_node script not found: {RUN_NODE_SCRIPT}")
    # Ensure not already running
    async with NODE_LOCK:
        current = NODE_PROCS.get(node_id)
        if _proc_is_running(current):
            return False
    cmd = [
        sys.executable,
        str(RUN_NODE_SCRIPT),
        "--id",
        node_id,
        "--config",
        str(CLUSTER_CONFIG_PATH),
        "--data-root",
        str(DATA_ROOT),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    if proc.returncode is not None:
        raise RuntimeError(f"Node {node_id} exited immediately (code {proc.returncode})")
    async with NODE_LOCK:
        NODE_PROCS[node_id] = proc
    asyncio.create_task(_monitor_proc(node_id, proc))
    return True


async def _kill_node(node_id: str, *, must_exist: bool = True) -> bool:
    async with NODE_LOCK:
        proc = NODE_PROCS.get(node_id)
    if not _proc_is_running(proc):
        if must_exist:
            raise RuntimeError(f"Node {node_id} is not running")
        return False
    assert proc is not None  # for type checker
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    finally:
        async with NODE_LOCK:
            existing = NODE_PROCS.get(node_id)
            if existing is proc:
                NODE_PROCS.pop(node_id, None)
    return True


async def _kill_all_nodes() -> None:
    async with NODE_LOCK:
        running_ids = list(NODE_PROCS.keys())
    for node_id in running_ids:
        try:
            await _kill_node(node_id, must_exist=False)
        except Exception:
            continue


@app.post("/cluster/start")
async def start_cluster() -> Dict[str, Any]:
    try:
        nodes = _load_cluster_nodes(strict=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load cluster config: {exc}") from exc

    started: List[str] = []
    already: List[str] = []
    errors: List[Dict[str, str]] = []

    for node in nodes:
        node_id = str(node["id"])
        try:
            created = await _start_node(node_id)
            if created:
                started.append(node_id)
            else:
                already.append(node_id)
        except Exception as exc:  # noqa: BLE001
            errors.append({"node": node_id, "error": str(exc)})

    status = "ok"
    if errors:
        status = "partial" if started else "error"
    return {
        "status": status,
        "started": started,
        "already_running": already,
        "errors": errors,
    }


@app.post("/cluster/node/{node_id}/kill")
async def kill_node(node_id: str) -> Dict[str, Any]:
    if node_id not in _node_ids():
        raise HTTPException(status_code=404, detail=f"Unknown node {node_id}")
    try:
        await _kill_node(node_id, must_exist=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "node": node_id, "action": "killed"}


@app.post("/cluster/node/{node_id}/restart")
async def restart_node(node_id: str) -> Dict[str, Any]:
    if node_id not in _node_ids():
        raise HTTPException(status_code=404, detail=f"Unknown node {node_id}")
    killed = False
    try:
        killed = await _kill_node(node_id, must_exist=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if killed:
        await asyncio.sleep(0.2)
    try:
        await _start_node(node_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "status": "ok",
        "node": node_id,
        "action": "restarted" if killed else "started",
    }


@app.on_event("shutdown")
async def _shutdown_cleanup() -> None:
    await _kill_all_nodes()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=APP_PORT, reload=False)
