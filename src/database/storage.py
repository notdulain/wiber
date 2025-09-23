import json
import os
from pathlib import Path
from typing import List, Dict
from ..config.settings import DATA_DIR

DATA_PATH = Path(DATA_DIR)


def _ensure_topic_path(topic: str) -> Path:
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    return DATA_PATH / f"{topic}.log"


def append_message(topic: str, ts: float, message: str) -> None:
    """Append a message to the topic log as JSONL."""
    log_path = _ensure_topic_path(topic)
    record = {"ts": ts, "msg": message}
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
