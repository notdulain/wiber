"""High-level DM API built on top of the Raft-backed messaging layer."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# wire imports for future REST/gateway, not needed yet
# from .wire import start_api_server


@dataclass
class DMMessage:
    msg_id: str
    sender: str
    text: str
    ts: float
    corrected_ts: float
    logical_time: Optional[int] = None


@dataclass
class DMHistory:
    conversation_id: str
    messages: List[DMMessage]


class DMClient:
    """Helper for DM operations on top of the node API."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    # In phase 8 we can add HTTP/REST here


def make_dm_topic(user_a: str, user_b: str) -> str:
    users = sorted([user_a, user_b])
    return f"dm:{users[0]}:{users[1]}"


class DMRegistry:
    """Stores minimal metadata for DM conversations (participants, display name)."""

    def __init__(self, base_dir: str | Path = ".data/dms"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _meta_path(self, convo_id: str) -> Path:
        return self.base_dir / f"{convo_id}.json"

    def ensure_conversation(self, convo_id: str, participants: List[str]) -> None:
        path = self._meta_path(convo_id)
        if path.exists():
            return
        meta = {
            "conversation_id": convo_id,
            "participants": participants,
            "created_at": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    def list_conversations(self) -> List[Dict]:
        out: List[Dict] = []
        for path in self.base_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
        return out

