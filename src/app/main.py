import asyncio
import json
import os
import threading
from typing import Dict, Set, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from confluent_kafka import Producer, Consumer
from datetime import datetime

# Bootstrap can list multiple brokers for resilience (recommended)
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092,localhost:9094,localhost:9096")
TOPIC = os.getenv("CHAT_TOPIC", "chat")

app = FastAPI(title="Wiber Gateway")

# In-memory mapping: room -> set(websockets)
rooms: Dict[str, Set[WebSocket]] = {}
ASGI_LOOP: Optional[asyncio.AbstractEventLoop] = None

# Kafka producer (idempotent, acks=all)
producer = Producer({
    "bootstrap.servers": BOOTSTRAP,
    "enable.idempotence": True,
    "acks": "all",
})


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.post("/api/send")
async def send_message(req: Request):
    body = await req.json()
    room = body.get("room_id", "general")
    msg = {
        "message_id": body.get("message_id"),
        "room_id": room,
        "user_id": body.get("user_id", "anon"),
        "event_time": body.get("event_time") or now_iso(),
        "server_time": now_iso(),
        "lamport_time": body.get("lamport_time"),  # optional extension
        "text": body.get("text", ""),
    }
    payload = json.dumps(msg).encode("utf-8")
    # Key by room to preserve per-room ordering
    producer.produce(TOPIC, key=room.encode(), value=payload)
    producer.flush(2)
    return {"status": "ok"}


@app.websocket("/ws/{room_id}")
async def ws_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    rooms.setdefault(room_id, set()).add(websocket)
    try:
        # Keep the connection open; clients don't need to send data
        while True:
            try:
                await websocket.receive_text()
            except Exception:
                await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        rooms[room_id].discard(websocket)


async def _broadcast_coro(room: str, text: str):
    """Coroutine that sends text to all clients in a room, pruning broken sockets."""
    dead: List[WebSocket] = []
    for ws in rooms.get(room, set()):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        rooms[room].discard(ws)


def broadcast(room: str, text: str):
    """Schedule a broadcast onto the running ASGI loop from any thread."""
    if ASGI_LOOP is None:
        return
    fut = asyncio.run_coroutine_threadsafe(_broadcast_coro(room, text), ASGI_LOOP)
    # Best effort: avoid blocking; errors will surface in logs if any
    try:
        fut.result(timeout=0)
    except Exception:
        pass


def consumer_worker():
    c = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": "wiber-ui-consumers",
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    })
    c.subscribe([TOPIC])
    try:
        while True:
            m = c.poll(1.0)
            if m is None:
                continue
            if m.error():
                # Could log with structlog here
                continue
            room = (m.key() or b"").decode() or "general"
            payload = json.loads(m.value().decode())
            payload["_kafka"] = {
                "topic": m.topic(),
                "partition": m.partition(),
                "offset": m.offset(),
                "timestamp": m.timestamp(),
            }
            broadcast(room, json.dumps(payload))
    except Exception:
        # Could log
        pass
    finally:
        c.close()


@app.on_event("startup")
def _start_bg():
    global ASGI_LOOP
    ASGI_LOOP = asyncio.get_event_loop()
    t = threading.Thread(target=consumer_worker, daemon=True)
    t.start()


INDEX_HTML = """
<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<title>Wiber Chat</title>
<style>
body { font: 14px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
#log { border: 1px solid #ccc; padding: 10px; height: 320px; overflow: auto; }
small { color: #666; }
label { display:block; margin-top: 6px; }
</style>
</head>
<body>
<h1>Wiber Chat</h1>
<label>Room: <input id=\"room\" value=\"general\"/></label>
<label>User: <input id=\"user\" value=\"u1\"/></label>
<div id=\"log\"></div>
<label>Message: <input id=\"msg\" /></label>
<button id=\"send\">Send</button>

<script>
let ws;
const log = document.getElementById('log');
const roomInput = document.getElementById('room');
const userInput = document.getElementById('user');
const msgInput = document.getElementById('msg');
const sendBtn = document.getElementById('send');

function connect() {
  const room = roomInput.value || 'general';
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/${encodeURIComponent(room)}`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    const meta = data._kafka || {};
    const div = document.createElement('div');
    div.innerHTML = `<strong>${data.user_id}</strong>: ${data.text} <small>[${meta.topic} p${meta.partition} @${meta.offset}]</small>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  };
}

roomInput.addEventListener('change', connect);
connect();

sendBtn.addEventListener('click', async () => {
  const room = roomInput.value || 'general';
  const payload = {
    message_id: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()),
    room_id: room,
    user_id: userInput.value || 'anon',
    event_time: new Date().toISOString(),
    text: msgInput.value
  };
  await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  msgInput.value = '';
});
</script>
</body>
</html>
"""
