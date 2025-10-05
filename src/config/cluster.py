"""Static cluster configuration loader.

Loads and validates a YAML cluster configuration describing nodes in the
distributed messaging system. The configuration schema is intentionally
minimal for Task 0.2 and focuses on nodes with required fields:
id (str), host (str), port (int).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import yaml


@dataclass(frozen=True)
class NodeConfig:
    id: str
    host: str
    port: int


@dataclass(frozen=True)
class ClusterConfig:
    nodes: List[NodeConfig]

    def to_dict(self) -> Dict[str, List[Dict[str, object]]]:
        return {"nodes": [vars(n) for n in self.nodes]}


def _validate_node_dict(node: dict) -> NodeConfig:
    if not isinstance(node, dict):
        raise ValueError("Each node entry must be a mapping")

    required_fields = ["id", "host", "port"]
    for field in required_fields:
        if field not in node:
            raise ValueError(f"Node missing required field: {field}")

    node_id = node["id"]
    host = node["host"]
    port = node["port"]

    if not isinstance(node_id, str) or not node_id:
        raise ValueError("Node 'id' must be a non-empty string")
    if not isinstance(host, str) or not host:
        raise ValueError("Node 'host' must be a non-empty string")
    if not isinstance(port, int) or port <= 0 or port > 65535:
        raise ValueError("Node 'port' must be an integer in range 1..65535")

    return NodeConfig(id=node_id, host=host, port=port)


def load_cluster_config(path: str) -> ClusterConfig:
    """Load and validate cluster configuration from a YAML file.

    Args:
        path: Path to YAML file containing cluster configuration.

    Returns:
        ClusterConfig: Parsed and validated configuration object.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("Top-level config must be a mapping")

    nodes_raw = data.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise ValueError("Config must include a non-empty 'nodes' list")

    nodes: List[NodeConfig] = []
    seen_ids: set[str] = set()
    for node in nodes_raw:
        node_cfg = _validate_node_dict(node)
        if node_cfg.id in seen_ids:
            raise ValueError(f"Duplicate node id: {node_cfg.id}")
        seen_ids.add(node_cfg.id)
        nodes.append(node_cfg)

    return ClusterConfig(nodes=nodes)

