#!/usr/bin/env python3
"""Tiny TCP JSONL echo/ack server for testing heartbeats/replication.

- Listens on one or more ports and prints any JSON line received.
- For messages with {"type": "replicate"}, replies with {"status": "ok"}.
- For messages with method "append_entries", replies with an
  append_entries_response(success=True).
- For heartbeats (custom), it just logs by default (optional ack).

Usage examples:
  # Start two peers on 9201 and 9202
  python scripts/tcp_ack_server.py --ports 9201,9202

  # Start one peer and also ACK heartbeats
  python scripts/tcp_ack_server.py --ports 9201 --ack-heartbeat
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import List


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ack_heartbeat: bool) -> None:
    addr = writer.get_extra_info("peername")
    try:
        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            try:
                obj = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            msg_type = obj.get("type")
            method = obj.get("method")
            print(f"recv from {addr}: {obj}")
            if msg_type == "replicate":
                writer.write((json.dumps({"status": "ok"}) + "\n").encode("utf-8"))
                await writer.drain()
            elif method == "append_entries":
                payload = obj.get("payload", {})
                writer.write((json.dumps({
                    "method": "append_entries_response",
                    "term": payload.get("term", 0),
                    "success": True,
                }) + "\n").encode("utf-8"))
                await writer.drain()
            elif msg_type == "heartbeat" and ack_heartbeat:
                writer.write((json.dumps({"status": "ok"}) + "\n").encode("utf-8"))
                await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def start_servers(host: str, ports: List[int], ack_heartbeat: bool) -> None:
    servers = []
    for port in ports:
        server = await asyncio.start_server(
            lambda r, w: handle_client(r, w, ack_heartbeat), host, port
        )
        print(f"listening on {host}:{port}")
        servers.append(server)
    try:
        await asyncio.gather(*(s.serve_forever() for s in servers))
    finally:
        for s in servers:
            s.close()
            try:
                await s.wait_closed()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny TCP JSONL echo/ack server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--ports", required=True, help="Comma-separated port list, e.g. 9201,9202")
    parser.add_argument("--ack-heartbeat", action="store_true", help="Send {status: ok} for heartbeat messages")
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    try:
        asyncio.run(start_servers(args.host, ports, args.ack_heartbeat))
    except KeyboardInterrupt:
        print("\nshutting down...")


if __name__ == "__main__":
    main()
