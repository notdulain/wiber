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

# Configuration
BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "9101"))
APP_PORT = int(os.getenv("GATEWAY_PORT", "8080"))

ROOT_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT_DIR / "public" / "index.html"

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


async def broker_command(command: str) -> List[str]:
    reader, writer = await asyncio.open_connection(BROKER_HOST, BROKER_PORT)
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
    reader, writer = await asyncio.open_connection(BROKER_HOST, BROKER_PORT)
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
        reader, writer = await asyncio.open_connection(BROKER_HOST, BROKER_PORT)
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
