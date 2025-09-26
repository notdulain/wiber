import asyncio
import time
from typing import Dict, Set, List

from ..config.settings import HOST, PORT
from ..database.storage import append_message, read_last

# Simple text protocol over TCP:
#  - SUB <topic> [group_id]        subscribe to a topic (optionally in a consumer group)
#  - PUB <topic> <message...>      publish a message
#  - HISTORY <topic> <n>           get last n messages
#  - ACK <message_id>              acknowledge message processing
#  - HEARTBEAT                     periodic "I'm alive" signal
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
        
        # ACK-related state
        self.pending_messages: Dict[asyncio.StreamWriter, List[Dict]] = {}
        self.ack_timeouts: Dict[str, float] = {}
        self.ack_timeout_seconds = 30.0  # 30 seconds timeout for ACKs
        
        # Heartbeat-related state
        self.last_heartbeat: Dict[asyncio.StreamWriter, float] = {}
        self.heartbeat_timeout_seconds = 30.0  # 30 seconds timeout for heartbeats
        
        # DLQ-related state
        self.message_retry_count: Dict[str, int] = {}  # Track retry count per message
        self.max_retries = 3  # Maximum retry attempts before DLQ
        self.retry_delays = [1, 2, 4]  # Exponential backoff delays in seconds

    async def start(self) -> None:
        server = await asyncio.start_server(self._handle_client, HOST, PORT)
        addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        print(f"Broker listening on {addr}")
        
        # Start monitoring tasks
        ack_monitor_task = asyncio.create_task(self._monitor_ack_timeouts())
        heartbeat_monitor_task = asyncio.create_task(self._monitor_heartbeats())
        dlq_monitor_task = asyncio.create_task(self._monitor_dlq_retries())
        
        try:
            async with server:
                await server.serve_forever()
        finally:
            ack_monitor_task.cancel()
            heartbeat_monitor_task.cancel()
            dlq_monitor_task.cancel()
            try:
                await ack_monitor_task
                await heartbeat_monitor_task
                await dlq_monitor_task
            except asyncio.CancelledError:
                pass

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        self.clients.add(writer)
        # Initialize heartbeat tracking for this client
        self.last_heartbeat[writer] = time.time()
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
                await self._send_line(writer, "ERR usage: HISTORY <topic> <n>")
                return
            topic, n_str = parts[1], parts[2]
            try:
                n = int(n_str)
            except ValueError:
                await self._send_line(writer, "ERR n must be an integer")
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

        if line.startswith("ACK "):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                await self._send_line(writer, "ERR usage: ACK <message_id>")
                return
            message_id = parts[1]
            await self._handle_ack(writer, message_id)
            return

        if line.upper() == "HEARTBEAT":
            await self._handle_heartbeat(writer)
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
        
        # Clean up pending messages for this consumer
        if writer in self.pending_messages:
            pending = self.pending_messages[writer]
            for msg in pending:
                message_id = msg.get("id")
                if message_id in self.ack_timeouts:
                    del self.ack_timeouts[message_id]
            del self.pending_messages[writer]
        
        # Clean up heartbeat tracking for this consumer
        if writer in self.last_heartbeat:
            del self.last_heartbeat[writer]
        
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
        """Distribute messages to consumer groups using round-robin with ACK support."""
        if topic not in self.consumer_groups:
            return
        
        # Extract message info for ACK tracking
        parts = line.split(maxsplit=5)
        if len(parts) >= 5:
            message_id = parts[2]
            offset = int(parts[3])
            ts = float(parts[4])
            message = parts[5] if len(parts) > 5 else ""
        else:
            return  # Invalid message format
        
        for group_id, consumers in self.consumer_groups[topic].items():
            if not consumers:
                continue
            
            # Find available consumer (not overloaded with pending messages)
            available_consumers = [
                c for c in consumers 
                if len(self.pending_messages.get(c, [])) < 5  # Max 5 pending messages per consumer
            ]
            
            if not available_consumers:
                print(f"All consumers in group '{group_id}' are busy, skipping message")
                continue
            
            # Round-robin: pick next available consumer in group
            group_key = f"{topic}:{group_id}"
            if group_key not in self.group_counters:
                self.group_counters[group_key] = 0
            
            # Get next available consumer (round-robin)
            consumer_index = self.group_counters[group_key] % len(available_consumers)
            target_consumer = available_consumers[consumer_index]
            
            # Send message to selected consumer
            try:
                await self._send_line(target_consumer, line)
                
                # Track pending message for ACK
                message_data = {
                    "id": message_id,
                    "offset": offset,
                    "ts": ts,
                    "msg": message,
                    "topic": topic,
                    "group_id": group_id,
                    "sent_time": time.time()
                }
                
                if target_consumer not in self.pending_messages:
                    self.pending_messages[target_consumer] = []
                self.pending_messages[target_consumer].append(message_data)
                self.ack_timeouts[message_id] = time.time()
                
                print(f"Sent message {message_id} to consumer {consumer_index + 1}/{len(available_consumers)} in group '{group_id}' (pending: {len(self.pending_messages[target_consumer])})")
            except Exception:
                dead.add(target_consumer)
            
            # Move to next consumer for next message
            self.group_counters[group_key] += 1

    async def _handle_ack(self, writer: asyncio.StreamWriter, message_id: str) -> None:
        """Handle ACK from consumer."""
        if writer not in self.pending_messages:
            await self._send_line(writer, "ERR no pending messages for this consumer")
            return
        
        # Find and remove the acknowledged message
        pending = self.pending_messages[writer]
        acked_message = None
        for i, msg in enumerate(pending):
            if msg["id"] == message_id:
                acked_message = pending.pop(i)
                break
        
        if acked_message:
            # Remove from timeout tracking
            if message_id in self.ack_timeouts:
                del self.ack_timeouts[message_id]
            
            print(f"ACK received for message {message_id} from consumer (remaining pending: {len(pending)})")
            await self._send_line(writer, "OK ack_received")
        else:
            await self._send_line(writer, f"ERR message {message_id} not found in pending messages")

    async def _monitor_ack_timeouts(self) -> None:
        """Monitor for ACK timeouts and handle them."""
        while True:
            try:
                current_time = time.time()
                timed_out_messages = []
                
                # Check for timed out messages
                for message_id, sent_time in self.ack_timeouts.items():
                    if current_time - sent_time > self.ack_timeout_seconds:
                        timed_out_messages.append(message_id)
                
                # Handle timed out messages
                for message_id in timed_out_messages:
                    await self._handle_ack_timeout(message_id)
                
                # Sleep for a short interval before checking again
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in ACK timeout monitor: {e}")
                await asyncio.sleep(5.0)

    async def _handle_ack_timeout(self, message_id: str) -> None:
        """Handle ACK timeout for a message - retry or send to DLQ."""
        print(f"ACK timeout for message {message_id}")
        
        # Find the consumer that has this pending message
        for consumer, pending in self.pending_messages.items():
            for i, msg in enumerate(pending):
                if msg["id"] == message_id:
                    # Remove the timed out message
                    timed_out_msg = pending.pop(i)
                    
                    # Remove from timeout tracking
                    if message_id in self.ack_timeouts:
                        del self.ack_timeouts[message_id]
                    
                    print(f"Removed timed out message {message_id} from consumer (remaining pending: {len(pending)})")
                    
                    # Handle retry or DLQ
                    await self._handle_message_retry_or_dlq(timed_out_msg)
                    return
        
        # If we get here, the message wasn't found in pending messages
        if message_id in self.ack_timeouts:
            del self.ack_timeouts[message_id]

    async def _handle_heartbeat(self, writer: asyncio.StreamWriter) -> None:
        """Handle heartbeat from consumer."""
        # Update last heartbeat time for this consumer
        self.last_heartbeat[writer] = time.time()
        print(f"Heartbeat received from consumer")
        await self._send_line(writer, "OK heartbeat_received")

    async def _monitor_heartbeats(self) -> None:
        """Monitor for heartbeat timeouts and handle dead consumers."""
        while True:
            try:
                current_time = time.time()
                dead_consumers = []
                
                # Check for consumers that haven't sent heartbeats
                for consumer, last_heartbeat_time in self.last_heartbeat.items():
                    if current_time - last_heartbeat_time > self.heartbeat_timeout_seconds:
                        dead_consumers.append(consumer)
                
                # Handle dead consumers
                for dead_consumer in dead_consumers:
                    await self._handle_dead_consumer(dead_consumer)
                
                # Sleep for a short interval before checking again
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(5.0)

    async def _handle_dead_consumer(self, dead_consumer: asyncio.StreamWriter) -> None:
        """Handle a dead consumer - redistribute pending messages and cleanup."""
        print(f"Consumer detected as dead - redistributing pending messages")
        
        # Get pending messages from dead consumer
        if dead_consumer in self.pending_messages:
            pending_messages = self.pending_messages[dead_consumer]
            print(f"Redistributing {len(pending_messages)} pending messages from dead consumer")
            
            # Redistribute each pending message to other consumers in the same group
            for msg in pending_messages:
                topic = msg.get("topic")
                group_id = msg.get("group_id")
                
                if topic and group_id and topic in self.consumer_groups:
                    if group_id in self.consumer_groups[topic]:
                        # Find alive consumers in the same group
                        alive_consumers = [
                            c for c in self.consumer_groups[topic][group_id]
                            if c != dead_consumer and c in self.last_heartbeat
                        ]
                        
                        if alive_consumers:
                            # Send message to first alive consumer
                            target_consumer = alive_consumers[0]
                            message_line = f"MSG {topic} {msg['id']} {msg['offset']} {msg['ts']} {msg['msg']}"
                            
                            try:
                                await self._send_line(target_consumer, message_line)
                                
                                # Track the redistributed message
                                if target_consumer not in self.pending_messages:
                                    self.pending_messages[target_consumer] = []
                                self.pending_messages[target_consumer].append(msg)
                                self.ack_timeouts[msg['id']] = time.time()
                                
                                print(f"Redistributed message {msg['id']} to alive consumer")
                            except Exception as e:
                                print(f"Failed to redistribute message {msg['id']}: {e}")
        
        # Clean up dead consumer
        self._disconnect(dead_consumer)

    async def _handle_message_retry_or_dlq(self, message: Dict) -> None:
        """Handle message retry or send to DLQ after failure."""
        message_id = message["id"]
        topic = message["topic"]
        group_id = message["group_id"]
        
        # Get current retry count
        retry_count = self.message_retry_count.get(message_id, 0)
        
        if retry_count < self.max_retries:
            # Retry the message
            retry_count += 1
            self.message_retry_count[message_id] = retry_count
            
            # Calculate delay for exponential backoff
            delay = self.retry_delays[min(retry_count - 1, len(self.retry_delays) - 1)]
            
            print(f"Retrying message {message_id} (attempt {retry_count}/{self.max_retries}) after {delay}s delay")
            
            # Schedule retry with delay
            asyncio.create_task(self._retry_message_with_delay(message, delay))
        else:
            # Send to DLQ
            print(f"Message {message_id} exceeded max retries, sending to DLQ")
            await self._send_to_dlq(message)

    async def _retry_message_with_delay(self, message: Dict, delay: float) -> None:
        """Retry a message after a delay."""
        await asyncio.sleep(delay)
        
        # Find alive consumers in the same group
        topic = message["topic"]
        group_id = message["group_id"]
        
        if topic in self.consumer_groups and group_id in self.consumer_groups[topic]:
            alive_consumers = [
                c for c in self.consumer_groups[topic][group_id]
                if c in self.last_heartbeat
            ]
            
            if alive_consumers:
                # Send to first available consumer
                target_consumer = alive_consumers[0]
                message_line = f"MSG {topic} {message['id']} {message['offset']} {message['ts']} {message['msg']}"
                
                try:
                    await self._send_line(target_consumer, message_line)
                    
                    # Track the retried message
                    if target_consumer not in self.pending_messages:
                        self.pending_messages[target_consumer] = []
                    self.pending_messages[target_consumer].append(message)
                    self.ack_timeouts[message['id']] = time.time()
                    
                    print(f"Retried message {message['id']} to consumer (retry attempt {self.message_retry_count[message['id']]})")
                except Exception as e:
                    print(f"Failed to retry message {message['id']}: {e}")
                    # If retry fails, send to DLQ
                    await self._send_to_dlq(message)
            else:
                print(f"No alive consumers for retry of message {message['id']}, sending to DLQ")
                await self._send_to_dlq(message)

    async def _send_to_dlq(self, message: Dict) -> None:
        """Send a failed message to the Dead Letter Queue."""
        dlq_topic = f"{message['topic']}.dlq"
        
        # Create DLQ message with additional metadata
        dlq_message = {
            "id": message["id"],
            "offset": message["offset"],
            "ts": message["ts"],
            "msg": message["msg"],
            "original_topic": message["topic"],
            "retry_count": self.message_retry_count.get(message["id"], 0),
            "dlq_timestamp": time.time(),
            "failure_reason": "max_retries_exceeded"
        }
        
        # Store in DLQ topic
        append_message(dlq_topic, dlq_message["dlq_timestamp"], str(dlq_message))
        
        # Clean up retry tracking
        if message["id"] in self.message_retry_count:
            del self.message_retry_count[message["id"]]
        
        print(f"Message {message['id']} sent to DLQ topic '{dlq_topic}'")

    async def _monitor_dlq_retries(self) -> None:
        """Monitor for DLQ retry scheduling (placeholder for future enhancements)."""
        while True:
            try:
                # This is a placeholder for future DLQ monitoring features
                # For now, we just sleep and let the system handle retries
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in DLQ monitor: {e}")
                await asyncio.sleep(10.0)

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
