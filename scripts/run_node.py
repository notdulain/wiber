#!/usr/bin/env python3
"""Run a single Wiber node as its own process.

Usage examples:
  - python scripts/run_node.py --id n1
  - python scripts/run_node.py --id n2 --config config/cluster.yaml

This lets IDEs (e.g., PyCharm) create one run configuration per node,
so you can start/stop/debug nodes individually.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Ensure repo root and src are on sys.path (similar to other scripts)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.config.cluster import load_cluster_config  # type: ignore
from src.cluster.node import Node  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single Wiber node")
    parser.add_argument(
        "--id",
        required=True,
        help="Node id to run (must exist in the cluster config)",
    )
    parser.add_argument(
        "--config",
        default=str((ROOT / "config" / "cluster.yaml").resolve()),
        help="Path to cluster config YAML (default: config/cluster.yaml)",
    )
    parser.add_argument(
        "--data-root",
        default=str((ROOT / ".data").resolve()),
        help="Base data directory for node state (default: .data)",
    )
    args = parser.parse_args()

    cfg = load_cluster_config(args.config)
    node_cfg = next((n for n in cfg.nodes if n.id == args.id), None)
    if node_cfg is None:
        raise SystemExit(f"Node id '{args.id}' not found in {args.config}")

    others = [(n.host, n.port) for n in cfg.nodes if n.id != node_cfg.id]

    node = Node(
        node_id=node_cfg.id,
        host=node_cfg.host,
        port=node_cfg.port,
        other_nodes=others,
        data_dir=str(Path(args.data_root) / node_cfg.id),
    )

    print(
        f"Starting node {node.node_id} at {node.host}:{node.port} with peers:"
    )
    for host, port in others:
        print(f"  - {host}:{port}")
    print("Press Ctrl+C to stop this node.")

    try:
        node.start()
    except KeyboardInterrupt:
        # node.start() already handles KeyboardInterrupt; this is a final guard
        pass


if __name__ == "__main__":
    main()

