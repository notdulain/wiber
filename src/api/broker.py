import asyncio
import time
from typing import Dict, Set

from ..config.settings import HOST, PORT
from ..database.storage import append_message, read_last

# Simple text protocol over TCP:
#  - SUB <topic> [group_id]        subscribe to a topic (optionally in a consumer group)
#  - PUB <topic> <message...>      publish a message
#  - HISTORY <topic> <n>           get last n messages
#  - PING                          health check
#  - QUIT                          close connection
#
# Server emits to subscribers:
#  - MSG <topic> <id> <offset> <ts> <message>
#  - HISTORY <topic> <id> <offset> <ts> <message>
#  - OK <description>
#  - ERR <description>


class Broker:
    def __init__(self) -> None:
        # Regular subscriptions (broadcast to all)
        self.subscriptions: Dict[str, Set[asyncio.StreamWriter]] = {}
        # Consumer groups (load balanced)
        self.consumer_groups: Dict[str, Dict[str, List[asyncio.StreamWriter]]] = {}
        self.clients: Set[asyncio.StreamWriter] = set()
        # Track which consumer gets which message (round-robin)
        self.group_counters: Dict[str, int] = {}

    async def start(self) -> None:
        server = await asyncio.start_server(self._handle_client, HOST, PORT)
        addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        print(f"Broker listening on {addr}")
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        self.clients.add(writer)
        print(f"Client connected: {peer}")
        await self._send_line(writer, "OK connected")
        try:
            while not reader.at_eof():
                raw = await reader.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    await self._handle_command(line, writer)
                except Exception as e:
                    await self._send_line(writer, f"ERR {type(e).__name__}: {e}")
        finally:
            self._disconnect(writer)
            print(f"Client disconnected: {peer}")

    async def _handle_command(self, line: str, writer: asyncio.StreamWriter) -> None:
        if line.upper() == "PING":
            await self._send_line(writer, "OK pong")
            return
        if line.upper() == "QUIT":
            await self._send_line(writer, "OK bye")
            writer.close()
            await writer.wait_closed()
            return

        # Commands with arguments
        if line.startswith("SUB "):
            parts = line.split()
            if len(parts) < 2:
                self._send_line(writer, "ERR usage: SUB <topic> [group_id]")
                return
            topic = parts[1]
            group_id = parts[2] if len(parts) > 2 else None
            
            if group_id:
                self._subscribe_to_group(topic, group_id, writer)
                await self._send_line(writer, f"OK subscribed {topic} in group {group_id}")
            else:
                self._subscribe(topic, writer)
                await self._send_line(writer, f"OK subscribed {topic}")
            return

        if line.startswith("PUB "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                self._send_line(writer, "ERR usage: PUB <topic> <message>")
                return
            topic, message = parts[1], parts[2]
            ts = time.time()
            append_message(topic, ts, message)
            # Get the message we just stored to get its ID and offset
            records = read_last(topic, 1)
            if records:
                record = records[0]
                message_id = record.get("id", "")
                offset = record.get("offset", 0)
                await self._broadcast(topic, message_id, offset, ts, message)
            await self._send_line(writer, "OK published")
            return

        if line.startswith("HISTORY "):
            parts = line.split(maxsplit=2)
            if len(parts) != 3:
                self._send_line(writer, "ERR usage: HISTORY <topic> <n>")
                return
            topic, n_str = parts[1], parts[2]
            try:
                n = int(n_str)
            except ValueError:
                self._send_line(writer, "ERR n must be an integer")
                return
            records = read_last(topic, n)
            for rec in records:
                message_id = rec.get("id", "")
                offset = rec.get("offset", 0)
                ts = rec.get("ts")
                msg = rec.get("msg", "")
                await self._send_line(writer, f"HISTORY {topic} {message_id} {offset} {ts} {msg}")
            await self._send_line(writer, "OK history end")
            return

        await self._send_line(writer, f"ERR unknown command: {line}")

    def _subscribe(self, topic: str, writer: asyncio.StreamWriter) -> None:
        self.subscriptions.setdefault(topic, set()).add(writer)

    def _subscribe_to_group(self, topic: str, group_id: str, writer: asyncio.StreamWriter) -> None:
        """Subscribe a client to a consumer group for a topic."""
        # Initialize topic groups if needed
        if topic not in self.consumer_groups:
            self.consumer_groups[topic] = {}
        
        # Initialize group if needed
        if group_id not in self.consumer_groups[topic]:
            self.consumer_groups[topic][group_id] = []
        
        # Add client to group
        self.consumer_groups[topic][group_id].append(writer)
        print(f"Client joined group '{group_id}' for topic '{topic}' (total: {len(self.consumer_groups[topic][group_id])})")

    def _disconnect(self, writer: asyncio.StreamWriter) -> None:
        # Remove from regular subscriptions
        for subs in self.subscriptions.values():
            subs.discard(writer)
        
        # Remove from consumer groups
        for topic_groups in self.consumer_groups.values():
            for group_consumers in topic_groups.values():
                if writer in group_consumers:
                    group_consumers.remove(writer)
        
        self.clients.discard(writer)
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass

    async def _broadcast(self, topic: str, message_id: str, offset: int, ts: float, message: str) -> None:
        line = f"MSG {topic} {message_id} {offset} {ts} {message}"
        dead: Set[asyncio.StreamWriter] = set()
        
        # Send to regular subscribers (broadcast)
        for w in self.subscriptions.get(topic, set()):
            try:
                await self._send_line(w, line)
            except Exception:
                dead.add(w)
        
        # Send to consumer groups (load balanced)
        await self._distribute_to_groups(topic, line, dead)
        
        # Clean up dead connections
        for w in dead:
            self._disconnect(w)

    async def _distribute_to_groups(self, topic: str, line: str, dead: Set[asyncio.StreamWriter]) -> None:
        """Distribute messages to consumer groups using round-robin."""
        if topic not in self.consumer_groups:
            return
        
        for group_id, consumers in self.consumer_groups[topic].items():
            if not consumers:
                continue
            
            # Round-robin: pick next consumer in group
            group_key = f"{topic}:{group_id}"
            if group_key not in self.group_counters:
                self.group_counters[group_key] = 0
            
            # Get next consumer (round-robin)
            consumer_index = self.group_counters[group_key] % len(consumers)
            target_consumer = consumers[consumer_index]
            
            # Send message to selected consumer
            try:
                await self._send_line(target_consumer, line)
                print(f"Sent message to consumer {consumer_index + 1}/{len(consumers)} in group '{group_id}'")
            except Exception:
                dead.add(target_consumer)
            
            # Move to next consumer for next message
            self.group_counters[group_key] += 1

    @staticmethod
    async def _send_line(writer: asyncio.StreamWriter, line: str) -> None:
        writer.write((line + "\n").encode("utf-8"))
        try:
            await writer.drain()
        except ConnectionResetError:
            # Client might have disconnected abruptly; ignore.
            pass


async def main() -> None:
    broker = Broker()
    await broker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBroker stopped by user")
