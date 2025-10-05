"""Static cluster configuration loader.

Parses a minimal YAML-like file with the following structure:

nodes:
  - id: n1
    host: 127.0.0.1
    port: 9101
  - id: n2
    host: 127.0.0.1
    port: 9102

If an explicit `leader_id:` is present at the top level, it is preferred.
Otherwise, the first node is chosen as the static leader for Phase 1.

Note: Implements a tiny, line-oriented parser to avoid external deps.
It supports only the exact subset used above.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class ClusterNode:
    id: str
    host: str
    port: int


@dataclass
class ClusterConfig:
    nodes: List[ClusterNode]
    leader_id: str


def _parse_minimal_yaml(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    result: Dict[str, Any] = {}
    nodes: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("leader_id:"):
            result["leader_id"] = line.split(":", 1)[1].strip()
            i += 1
            continue
        if line.startswith("nodes:"):
            i += 1
            # Expect a sequence of "- id: ..." blocks with indented key: value lines
            while i < len(lines) and lines[i].lstrip().startswith("-"):
                entry: Dict[str, Any] = {}
                # Parse first line with id
                first = lines[i].lstrip()[1:].strip()  # drop leading '-'
                if first:
                    k, v = [p.strip() for p in first.split(":", 1)]
                    entry[k] = _coerce(v)
                i += 1
                # Parse indented properties (assume up to next dash or dedent)
                while i < len(lines) and not lines[i].lstrip().startswith("-") and lines[i].startswith("  "):
                    kv = lines[i].strip()
                    if ":" in kv:
                        k, v = [p.strip() for p in kv.split(":", 1)]
                        entry[k] = _coerce(v)
                    i += 1
                nodes.append(entry)
            result["nodes"] = nodes
            continue
        i += 1
    return result


def _coerce(val: str):
    # try int
    try:
        return int(val)
    except ValueError:
        pass
    # strip quotes if present
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def load_cluster_config(path: str) -> ClusterConfig:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    data = _parse_minimal_yaml(text)
    raw_nodes = data.get("nodes") or []
    nodes = [ClusterNode(id=str(n.get("id")), host=str(n.get("host")), port=int(n.get("port"))) for n in raw_nodes]
    if not nodes:
        raise ValueError("No nodes defined in cluster config")
    leader_id = str(data.get("leader_id") or nodes[0].id)
    return ClusterConfig(nodes=nodes, leader_id=leader_id)

