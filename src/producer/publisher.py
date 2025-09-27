import argparse
import asyncio

from ..config.settings import HOST, PORT


async def publish(topic: str, message: str, host: str = None, port: int = None) -> None:
    # Use provided host/port or fall back to defaults
    connect_host = host or HOST
    connect_port = port or PORT
    reader, writer = await asyncio.open_connection(connect_host, connect_port)
    # Drain initial banner if any
    await reader.readline()
    writer.write(f"PUB {topic} {message}\n".encode("utf-8"))
    await writer.drain()
    resp = await reader.readline()
    print(resp.decode().strip())
    writer.write(b"QUIT\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publisher client")
    parser.add_argument("topic", help="Topic to publish to")
    parser.add_argument("message", help="Message content")
    parser.add_argument("--host", type=str, help="Broker host (default: from config)")
    parser.add_argument("--port", type=int, help="Broker port (default: from config)")
    args = parser.parse_args()
    asyncio.run(publish(args.topic, args.message, args.host, args.port))


if __name__ == "__main__":
    main()
