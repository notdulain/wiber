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
        return lines
    finally:
        writer.close()
        await writer.wait_closed()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=APP_PORT, reload=False)
