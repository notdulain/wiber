# simple TCP broker with per-topic offsets + HISTORY
import json, socket, threading
from typing import Dict, List

HOST, PORT = "0.0.0.0", 7777

_storage: Dict[str, List[dict]] = {}     # topic -> list of messages
_next_offset: Dict[str, int] = {}        # topic -> next offset

def append(topic: str, msg: dict):
    off = _next_offset.get(topic, 0)
    msg.setdefault("ts", 0)              # keep publisher's ms timestamp if present
    msg["offset"] = off                  # absolute order within topic
    _next_offset[topic] = off + 1
    _storage.setdefault(topic, []).append(msg)

def get_history(topic: str, limit: int | None = None) -> List[dict]:
    lst = _storage.get(topic, [])
    ordered = sorted(lst, key=lambda m: (m["offset"], m.get("id","")))
    if limit:
        ordered = ordered[-int(limit):]
    return ordered

def handle(conn: socket.socket):
    buf = conn.recv(1_000_000).decode().strip()
    try:
        if buf.startswith("PUB "):
            payload = json.loads(buf[4:])
            append(payload["topic"], payload)
            conn.sendall(b"OK\n")
        elif buf.startswith("HISTORY "):
            _, topic, *rest = buf.split()
            limit = int(rest[0]) if rest else None
            hist = get_history(topic, limit)
            conn.sendall((json.dumps(hist) + "\n").encode())
        else:
            conn.sendall(b"ERR unknown\n")
    except Exception as e:
        conn.sendall(f"ERR {e}\n".encode())
    finally:
        conn.close()

def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT)); s.listen()
        print(f"Broker on {HOST}:{PORT}")
        while True:
            c, _ = s.accept()
            threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    serve()