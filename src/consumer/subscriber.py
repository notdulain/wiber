import argparse
import asyncio

from ..config.settings import HOST, PORT


async def subscribe(topic: str, history: int) -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
    banner = await reader.readline()
    print(banner.decode().strip())

    # Subscribe to topic
    writer.write(f"SUB {topic}\n".encode("utf-8"))
    await writer.drain()
    print((await reader.readline()).decode().strip())

    # Optionally request last N messages
    if history > 0:
        writer.write(f"HISTORY {topic} {history}\n".encode("utf-8"))
        await writer.drain()

    # Read messages indefinitely
    try:
        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            print(line.decode().strip())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            writer.write(b"QUIT\n")
            await writer.drain()
        except Exception:
            pass
        writer.close()
        await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Subscriber client")
    parser.add_argument("topic", help="Topic to subscribe to")
    parser.add_argument("--history", type=int, default=0, help="Fetch last N messages on start")
    args = parser.parse_args()
    asyncio.run(subscribe(args.topic, args.history))


if __name__ == "__main__":
    main()
