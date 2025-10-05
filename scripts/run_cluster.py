#!/usr/bin/env python3
"""Run a local multi-node cluster and print heartbeats.

Usage:
  python scripts/run_cluster.py [config/cluster.yaml]
"""

import sys
import asyncio
from pathlib import Path

# Ensure repo root is on sys.path so `import src...` works when running this file
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.cluster import load_cluster_config
from src.cluster.node import Node


async def _run(config_path: str) -> None:
    cfg = load_cluster_config(config_path)
    # Start all nodes defined in config
    nodes = [Node(n.id, config_path=config_path) for n in cfg.nodes]
    await asyncio.gather(*(n.start() for n in nodes))
    print("cluster started. press Ctrl+C to stop.")
    # Run forever
    while True:
        await asyncio.sleep(1)


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/cluster.yaml"
    try:
        asyncio.run(_run(config_path))
    except KeyboardInterrupt:
        print("\nshutting down...")


if __name__ == "__main__":
    main()
