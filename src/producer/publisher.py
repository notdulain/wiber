import argparse
import asyncio

from ..config.settings import HOST, PORT


async def publish(topic: str, message: str) -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
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
    args = parser.parse_args()
    asyncio.run(publish(args.topic, args.message))


if __name__ == "__main__":
    main()
