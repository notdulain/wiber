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
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Wiber Chat</title>
<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.container {
  width: 100%;
  max-width: 800px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 90vh;
  max-height: 700px;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.header h1 {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.header-inputs {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.input-group label {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.9;
}

.input-group input {
  padding: 8px 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-radius: 8px;
  background: rgba(255,255,255,0.15);
  color: white;
  font-size: 14px;
  width: 120px;
  transition: all 0.2s;
}

.input-group input::placeholder {
  color: rgba(255,255,255,0.6);
}

.input-group input:focus {
  outline: none;
  background: rgba(255,255,255,0.25);
  border-color: rgba(255,255,255,0.5);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f8f9fa;
}

.message {
  margin-bottom: 16px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-content {
  background: white;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border-left: 3px solid #667eea;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.message-user {
  font-weight: 600;
  color: #667eea;
  font-size: 14px;
}

.message-meta {
  font-size: 11px;
  color: #999;
  font-family: 'Courier New', monospace;
}

.message-text {
  color: #333;
  font-size: 15px;
  line-height: 1.5;
  word-wrap: break-word;
}

.input-area {
  padding: 20px 24px;
  background: white;
  border-top: 1px solid #e9ecef;
  display: flex;
  gap: 12px;
}

.input-area input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e9ecef;
  border-radius: 10px;
  font-size: 15px;
  transition: all 0.2s;
}

.input-area input:focus {
  outline: none;
  border-color: #667eea;
}

.input-area button {
  padding: 12px 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.input-area button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.input-area button:active {
  transform: translateY(0);
}

.status-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4ade80;
  margin-right: 8px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-state svg {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
  opacity: 0.3;
}

.empty-state p {
  font-size: 16px;
}

/* Scrollbar styling */
.messages::-webkit-scrollbar {
  width: 8px;
}

.messages::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.messages::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 4px;
}

.messages::-webkit-scrollbar-thumb:hover {
  background: #999;
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div style="display: flex; align-items: center;">
      <span class="status-indicator"></span>
      <h1>Wiber Chat</h1>
    </div>
    <div class="header-inputs">
      <div class="input-group">
        <label>Room:</label>
        <input id="room" value="general" placeholder="general"/>
      </div>
      <div class="input-group">
        <label>User:</label>
        <input id="user" value="u1" placeholder="Username"/>
      </div>
    </div>
  </div>
  
  <div class="messages" id="log">
    <div class="empty-state">
      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
      </svg>
      <p>No messages yet. Start the conversation!</p>
    </div>
  </div>
  
  <div class="input-area">
    <input id="msg" placeholder="Type your message..." />
    <button id="send">Send</button>
  </div>
</div>

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
    // Remove empty state if it exists
    const emptyState = log.querySelector('.empty-state');
    if (emptyState) {
      emptyState.remove();
    }
    
    const data = JSON.parse(ev.data);
    const meta = data._kafka || {};
    
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message';
    msgDiv.innerHTML = `
      <div class="message-content">
        <div class="message-header">
          <span class="message-user">${escapeHtml(data.user_id)}</span>
          <span class="message-meta">${meta.topic || ''} p${meta.partition || ''} @${meta.offset || ''}</span>
        </div>
        <div class="message-text">${escapeHtml(data.text)}</div>
      </div>
    `;
    log.appendChild(msgDiv);
    log.scrollTop = log.scrollHeight;
  };
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

roomInput.addEventListener('change', connect);
connect();

async function sendMessage() {
  const text = msgInput.value.trim();
  if (!text) return;
  
  const room = roomInput.value || 'general';
  const payload = {
    message_id: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()),
    room_id: room,
    user_id: userInput.value || 'anon',
    event_time: new Date().toISOString(),
    text: text
  };
  
  await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  msgInput.value = '';
}

sendBtn.addEventListener('click', sendMessage);
msgInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    sendMessage();
  }
});
</script>
</body>
</html>
"""