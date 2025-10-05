"""Text-based wire protocol for clients.

Supported commands:
- PING -> PONG
- PUB <topic> <message> -> OK <offset> or ERR <reason>
- SUB <topic> -> OK or ERR <reason>
- HISTORY <topic> [offset] [limit] -> OK <messages> or ERR <reason>
- TOPICS -> OK <topics_list> or ERR <reason>
- STATS [topic] -> OK <stats> or ERR <reason>
- HELP -> OK <help_text> or ERR <reason>
- QUIT -> disconnect
"""

from __future__ import annotations

import asyncio
import json
import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger(__name__)


class WireProtocolHandler:
    """Handles wire protocol commands for clients."""
    
    def __init__(self, topic_manager=None, raft=None):
        """Initialize the wire protocol handler.
        
        Args:
            topic_manager: TopicManager instance for message operations
            raft: Raft instance for message replication
        """
        self.topic_manager = topic_manager
        self.raft = raft
        self.subscribers: Dict[str, set] = {}  # topic -> set of writers
        
    async def handle_command(self, command: str, writer: asyncio.StreamWriter) -> None:
        """Handle a single command from a client.
        
        Args:
            command: The command string from the client
            writer: Stream writer to send response
        """
        try:
            parts = command.strip().split()
            if not parts:
                await self._send_error(writer, "Empty command")
                return
            
            cmd = parts[0].upper()
            
            if cmd == "PING":
                await self._handle_ping(writer)
            elif cmd == "PUB":
                await self._handle_pub(parts, writer)
            elif cmd == "SUB":
                await self._handle_sub(parts, writer)
            elif cmd == "HISTORY":
                await self._handle_history(parts, writer)
            elif cmd == "TOPICS":
                await self._handle_topics(writer)
            elif cmd == "STATS":
                await self._handle_stats(parts, writer)
            elif cmd == "HELP":
                await self._handle_help(writer)
            else:
                await self._send_error(writer, f"Unknown command: {cmd}")
                
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            await self._send_error(writer, f"Internal error: {str(e)}")
    
    async def _handle_ping(self, writer: asyncio.StreamWriter) -> None:
        """Handle PING command."""
        await self._send_response(writer, "PONG")
    
    async def _handle_pub(self, parts: list, writer: asyncio.StreamWriter) -> None:
        """Handle PUB command: PUB <topic> <message>."""
        if len(parts) < 3:
            await self._send_error(writer, "Usage: PUB <topic> <message>")
            return
        
        topic = parts[1]
        message = " ".join(parts[2:])  # Join remaining parts as message
        
        if not self.topic_manager:
            await self._send_error(writer, "Topic manager not available")
            return
        
        # Check if topic exists
        if topic not in self.topic_manager.topics:
            await self._send_error(writer, f"Topic '{topic}' does not exist")
            return
        
        # Create message object
        message_obj = {
            "content": message,
            "timestamp": asyncio.get_event_loop().time(),
            "client": "wire_protocol",
            "topic": topic
        }
        
        # If we have Raft, use it for replication
        if self.raft and self.raft.state.value == "leader":
            # Use Raft for replication
            success = self.raft.add_entry("PUB", message_obj)
            if success:
                await self._send_response(writer, f"OK replicated")
                logger.info(f"Published message to topic '{topic}' via Raft")
            else:
                await self._send_error(writer, "Failed to replicate message")
        else:
            # Fallback to direct topic manager (for testing)
            offset = self.topic_manager.publish_message(topic, message_obj)
            if offset >= 0:
                await self._send_response(writer, f"OK {offset}")
                logger.info(f"Published message to topic '{topic}' at offset {offset}")
            else:
                await self._send_error(writer, "Failed to publish message")
    
    async def _handle_sub(self, parts: list, writer: asyncio.StreamWriter) -> None:
        """Handle SUB command: SUB <topic>."""
        if len(parts) < 2:
            await self._send_error(writer, "Usage: SUB <topic>")
            return
        
        topic = parts[1]
        
        if not self.topic_manager:
            await self._send_error(writer, "Topic manager not available")
            return
        
        # Check if topic exists
        if topic not in self.topic_manager.topics:
            await self._send_error(writer, f"Topic '{topic}' does not exist")
            return
        
        # Add to subscribers
        if topic not in self.subscribers:
            self.subscribers[topic] = set()
        self.subscribers[topic].add(writer)
        
        await self._send_response(writer, f"OK subscribed to {topic}")
        logger.info(f"Client subscribed to topic '{topic}'")
    
    async def _handle_history(self, parts: list, writer: asyncio.StreamWriter) -> None:
        """Handle HISTORY command: HISTORY <topic> [offset] [limit]."""
        if len(parts) < 2:
            await self._send_error(writer, "Usage: HISTORY <topic> [offset] [limit]")
            return
        
        topic = parts[1]
        offset = int(parts[2]) if len(parts) > 2 else 0
        limit = int(parts[3]) if len(parts) > 3 else 10
        
        if not self.topic_manager:
            await self._send_error(writer, "Topic manager not available")
            return
        
        # Check if topic exists
        if topic not in self.topic_manager.topics:
            await self._send_error(writer, f"Topic '{topic}' does not exist")
            return
        
        # Get messages from topic
        messages = self.topic_manager.read_messages(topic, offset, limit)
        
        # Format response
        response_data = {
            "topic": topic,
            "offset": offset,
            "limit": limit,
            "count": len(messages),
            "messages": messages
        }
        
        await self._send_response(writer, f"OK {json.dumps(response_data)}")
        logger.info(f"Retrieved {len(messages)} messages from topic '{topic}'")
    
    async def _handle_topics(self, writer: asyncio.StreamWriter) -> None:
        """Handle TOPICS command: list all available topics."""
        if not self.topic_manager:
            await self._send_error(writer, "Topic manager not available")
            return
        
        topics_list = []
        for topic_name, topic_info in self.topic_manager.topics.items():
            topics_list.append({
                "name": topic_name,
                "description": topic_info.get("description", ""),
                "retention_hours": topic_info.get("retention_hours", 0),
                "max_messages": topic_info.get("max_messages", 0)
            })
        
        response_data = {
            "topics": topics_list,
            "count": len(topics_list)
        }
        
        await self._send_response(writer, f"OK {json.dumps(response_data)}")
        logger.info(f"Listed {len(topics_list)} topics")
    
    async def _handle_stats(self, parts: list, writer: asyncio.StreamWriter) -> None:
        """Handle STATS command: STATS [topic]."""
        if not self.topic_manager:
            await self._send_error(writer, "Topic manager not available")
            return
        
        if len(parts) > 1:
            # Stats for specific topic
            topic = parts[1]
            if topic not in self.topic_manager.topics:
                await self._send_error(writer, f"Topic '{topic}' does not exist")
                return
            
            # Get topic-specific stats using the correct API
            topic_info = self.topic_manager.get_topic_info(topic)
            if topic_info:
                response_data = {
                    "topic": topic,
                    "message_count": topic_info.get("current_message_count", 0),
                    "latest_offset": topic_info.get("latest_offset", -1),
                    "deduplication_enabled": topic_info.get("deduplication_enabled", False),
                    "subscriber_count": len(self.subscribers.get(topic, set()))
                    if topic in self.subscribers else 0,
                    "retention_hours": topic_info.get("retention_hours", 0),
                    "max_messages": topic_info.get("max_messages", 0)
                }
            else:
                response_data = {
                    "topic": topic,
                    "message_count": 0,
                    "latest_offset": -1,
                    "deduplication_enabled": False,
                    "subscriber_count": 0
                }
        else:
            # Overall cluster stats
            total_messages = 0
            total_subscribers = 0
            for topic_name in self.topic_manager.topics.keys():
                topic_info = self.topic_manager.get_topic_info(topic_name)
                if topic_info:
                    total_messages += topic_info.get("current_message_count", 0)
                total_subscribers += len(self.subscribers.get(topic_name, set()))
            
            response_data = {
                "cluster": {
                    "total_topics": len(self.topic_manager.topics),
                    "total_messages": total_messages,
                    "total_subscribers": total_subscribers
                }
            }
        
        await self._send_response(writer, f"OK {json.dumps(response_data)}")
        logger.info(f"Retrieved stats for {'topic' if len(parts) > 1 else 'cluster'}")
    
    async def _handle_help(self, writer: asyncio.StreamWriter) -> None:
        """Handle HELP command: show available commands."""
        help_text = {
            "commands": [
                {
                    "command": "PING",
                    "description": "Test connection to server",
                    "usage": "PING"
                },
                {
                    "command": "PUB",
                    "description": "Publish a message to a topic",
                    "usage": "PUB <topic> <message>"
                },
                {
                    "command": "SUB",
                    "description": "Subscribe to a topic for real-time messages",
                    "usage": "SUB <topic>"
                },
                {
                    "command": "HISTORY",
                    "description": "Get message history from a topic",
                    "usage": "HISTORY <topic> [offset] [limit]"
                },
                {
                    "command": "TOPICS",
                    "description": "List all available topics",
                    "usage": "TOPICS"
                },
                {
                    "command": "STATS",
                    "description": "Get statistics for a topic or cluster",
                    "usage": "STATS [topic]"
                },
                {
                    "command": "HELP",
                    "description": "Show this help message",
                    "usage": "HELP"
                },
                {
                    "command": "QUIT",
                    "description": "Exit the client",
                    "usage": "QUIT"
                }
            ]
        }
        
        await self._send_response(writer, f"OK {json.dumps(help_text)}")
        logger.info("Provided help information")
    
    async def _send_response(self, writer: asyncio.StreamWriter, message: str) -> None:
        """Send a success response to the client."""
        response = f"{message}\n"
        writer.write(response.encode("utf-8"))
        await writer.drain()
    
    async def _send_error(self, writer: asyncio.StreamWriter, error: str) -> None:
        """Send an error response to the client."""
        response = f"ERR {error}\n"
        writer.write(response.encode("utf-8"))
        await writer.drain()
    
    def remove_subscriber(self, writer: asyncio.StreamWriter) -> None:
        """Remove a subscriber from all topics."""
        for topic, subscribers in self.subscribers.items():
            subscribers.discard(writer)
    
    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to all subscribers of a topic."""
        if topic not in self.subscribers:
            return
        
        # Create broadcast message
        broadcast_msg = f"MSG {topic} {json.dumps(message)}\n"
        
        # Send to all subscribers
        disconnected = set()
        for writer in self.subscribers[topic]:
            try:
                writer.write(broadcast_msg.encode("utf-8"))
                await writer.drain()
            except Exception:
                # Client disconnected
                disconnected.add(writer)
        
        # Remove disconnected clients
        for writer in disconnected:
            self.subscribers[topic].discard(writer)


# Global handler instance
_handler: Optional[WireProtocolHandler] = None


def set_topic_manager(topic_manager, raft=None):
    """Set the topic manager and raft instance for the wire protocol handler."""
    global _handler
    if _handler is None:
        _handler = WireProtocolHandler(topic_manager, raft)
    else:
        _handler.topic_manager = topic_manager
        _handler.raft = raft


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle a client connection."""
    global _handler
    
    try:
        # Keep connection open for multiple commands
        while True:
            # Read command
            data = await reader.readline()
            if not data:
                break  # Client disconnected
            
            command = data.decode("utf-8").strip()
            logger.debug(f"Received command: {command}")
            
            # Handle command
            if _handler:
                await _handler.handle_command(command, writer)
            else:
                # Fallback to basic PING/PONG
                if command.upper() == "PING":
                    writer.write(b"PONG\n")
                    await writer.drain()
                else:
                    writer.write(b"ERR topic manager not available\n")
                    await writer.drain()
                    
    except Exception as e:
        logger.error(f"Error handling client: {e}")
        try:
            writer.write(b"ERR internal error\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        # Clean up subscriber
        if _handler:
            _handler.remove_subscriber(writer)
        
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def create_api_server(host: str, port: int) -> asyncio.AbstractServer:
    """Create the API server (does not block). Useful for tests."""
    server = await asyncio.start_server(_handle_client, host, port)
    return server


async def _serve_forever(host: str, port: int) -> None:
    server = await create_api_server(host, port)
    async with server:
        await server.serve_forever()


def start_api_server(host: str, port: int) -> None:
    """Start client API server and block forever."""
    asyncio.run(_serve_forever(host, port))

