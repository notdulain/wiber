import json
import os
import time
import uuid
from pathlib import Path
from typing import List, Dict
from ..config.settings import DATA_DIR

DATA_PATH = Path(DATA_DIR)


def _ensure_topic_path(topic: str) -> Path:
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    return DATA_PATH / f"{topic}.log"


def _get_next_offset(topic: str) -> int:
    """Get the next offset for a topic by counting existing messages."""
    log_path = _ensure_topic_path(topic)
    if not log_path.exists():
        return 1  # First message gets offset 1
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return len(lines) + 1
    except FileNotFoundError:
        return 1


def append_message(topic: str, ts: float, message: str) -> None:
    """Append a message to the topic log as JSONL with ID and offset."""
    log_path = _ensure_topic_path(topic)
    
    # Generate unique message ID and offset
    message_id = f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    offset = _get_next_offset(topic)
    
    record = {
        "id": message_id,
        "offset": offset,
        "ts": ts,
        "msg": message
    }
    
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_last(topic: str, n: int) -> List[Dict]:
    """Read the last n messages from the topic log. Returns list of dicts."""
    log_path = _ensure_topic_path(topic)
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    out: List[Dict] = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
