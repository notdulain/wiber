"""RPC transport for inter-node communication.

Simple TCP/JSON protocol for nodes to send messages to each other.
Supports basic ping/pong for Phase 1, will extend for Raft in Phase 2.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RpcServer:
    """RPC server for receiving messages from other nodes."""
    
    def __init__(self, host: str, port: int, node_id: str):
        self.host = host
        self.port = port
        self.node_id = node_id
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        """Start the RPC server."""
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        logger.info(f"RPC server started on {self.host}:{self.port}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming RPC requests."""
        try:
            # Read the JSON message
            data = await reader.readline()
            if not data:
                return
                
            message = json.loads(data.decode("utf-8"))
            logger.debug(f"Received RPC: {message}")
            
            # Handle the request
            response = await self._process_request(message)
            
            # Send response
            response_data = json.dumps(response) + "\n"
            writer.write(response_data.encode("utf-8"))
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error handling RPC request: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming RPC request."""
        method = message.get("method")
        
        if method == "ping":
            return {
                "method": "pong",
                "from": self.node_id,
                "timestamp": asyncio.get_event_loop().time()
            }
        else:
            return {
                "method": "error",
                "error": f"Unknown method: {method}"
            }

    async def stop(self) -> None:
        """Stop the RPC server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("RPC server stopped")


class RpcClient:
    """RPC client for sending messages to other nodes."""
    
    def __init__(self, host: str, port: int, node_id: str):
        self.host = host
        self.port = port
        self.node_id = node_id

    async def call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send RPC request to another node."""
        if payload is None:
            payload = {}
            
        message = {
            "method": method,
            "from": self.node_id,
            "payload": payload,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            
            # Send request
            request_data = json.dumps(message) + "\n"
            writer.write(request_data.encode("utf-8"))
            await writer.drain()
            
            # Read response
            response_data = await reader.readline()
            response = json.loads(response_data.decode("utf-8"))
            
            writer.close()
            await writer.wait_closed()
            
            logger.debug(f"RPC call {method} -> {response}")
            return response
            
        except Exception as e:
            logger.error(f"RPC call failed to {self.host}:{self.port}: {e}")
            return {
                "method": "error",
                "error": str(e)
            }

    async def ping(self) -> Dict[str, Any]:
        """Send ping to another node."""
        return await self.call("ping")

