#!/usr/bin/env python3
"""Start a minimal single-node instance from config (Task 0.3/0.4).

Loads the first node from `config/cluster.yaml` and starts an API server that
responds to PING. Future iterations will add multi-node and Raft.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from config.cluster import load_cluster_config  # type: ignore
from cluster.node import Node  # type: ignore


def main() -> None:
    cfg_path = str((ROOT / "config" / "cluster.yaml").resolve())
    cfg = load_cluster_config(cfg_path)

    # Start the first node in the list for now
    n0 = cfg.nodes[0]
    node = Node(node_id=n0.id, host=n0.host, port=n0.port)
    print(f"Starting node {n0.id} on {n0.host}:{n0.port} (PING -> PONG)")
    node.start()


if __name__ == "__main__":
    main()

