#!/usr/bin/env python3
"""Simple DM demo on top of the wire protocol."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api.dm_api import make_dm_topic


def _subscribe(host: str, port: int, convo_id: str, history: int = 5):
    async def run():
        reader, writer = await asyncio.open_connection(host, port)
        if history > 0:
            writer.write(f"HISTORY {convo_id} {history}\n".encode())
            await writer.drain()
            while True:
                line = await reader.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                print("[history]", decoded)
                if decoded == "OK history_end":
                    break
        writer.write(f"SUB {convo_id}\n".encode())
        await writer.drain()
        print("Subscribed to", convo_id)
        while True:
            line = await reader.readline()
            if not line:
                break
            print("[live]", line.decode().strip())
    asyncio.run(run())


def _publish(host: str, port: int, convo_id: str, message: str, msg_id: str | None = None):
    async def run():
        reader, writer = await asyncio.open_connection(host, port)
        cmd = f"PUB {convo_id} {message}" if not msg_id else f"PUB {convo_id} --id {msg_id} {message}"
        writer.write((cmd + "\n").encode())
        await writer.drain()
        print((await reader.readline()).decode().strip())
        writer.close()
        await writer.wait_closed()
    asyncio.run(run())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DM demo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_topic = sub.add_parser("topic", help="Print DM topic for two users")
    p_topic.add_argument("user_a")
    p_topic.add_argument("user_b")

    p_pub = sub.add_parser("send", help="Send a DM")
    p_pub.add_argument("user_a")
    p_pub.add_argument("user_b")
    p_pub.add_argument("message")
    p_pub.add_argument("--host", default="127.0.0.1")
    p_pub.add_argument("--port", type=int, default=9101)
    p_pub.add_argument("--id", dest="msg_id")

    p_sub = sub.add_parser("listen", help="Listen to DMs")
    p_sub.add_argument("user_a")
    p_sub.add_argument("user_b")
    p_sub.add_argument("--host", default="127.0.0.1")
    p_sub.add_argument("--port", type=int, default=9101)
    p_sub.add_argument("--history", type=int, default=5)

    args = parser.parse_args()

    if args.cmd == "topic":
        print(make_dm_topic(args.user_a, args.user_b))
    elif args.cmd == "send":
        topic = make_dm_topic(args.user_a, args.user_b)
        _publish(args.host, args.port, topic, args.message, args.msg_id)
    elif args.cmd == "listen":
        topic = make_dm_topic(args.user_a, args.user_b)
        _subscribe(args.host, args.port, topic, args.history)

