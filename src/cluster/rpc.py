"""RPC transport for inter-node communication.

Simple TCP/JSON protocol for nodes to send messages to each other.
Supports basic ping/pong for Phase 1, will extend for Raft in Phase 2.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from cluster.raft import RaftState

logger = logging.getLogger(__name__)


class RpcServer:
    """RPC server for receiving messages from other nodes."""
    
    def __init__(self, host: str, port: int, node_id: str, raft_instance=None):
        self.host = host
        self.port = port
        self.node_id = node_id
        self.raft = raft_instance  # Will be set by Node
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
        elif method == "request_vote":
            # Handle RequestVote RPC for Raft elections
            payload = message.get("payload", {})
            candidate_id = payload.get("candidate_id")
            candidate_term = payload.get("candidate_term", 0)
            last_log_index = payload.get("last_log_index", 0)
            last_log_term = payload.get("last_log_term", 0)
            
            # Connect to Raft if available
            if self.raft:
                response = self.raft.handle_request_vote(
                    candidate_id, candidate_term, last_log_index, last_log_term
                )
                return {
                    "method": "request_vote_response",
                    "term": response["term"],
                    "vote_granted": response["vote_granted"],
                    "from": self.node_id
                }
            else:
                # Fallback if Raft not connected
                return {
                    "method": "request_vote_response",
                    "term": candidate_term,
                    "vote_granted": True,
                    "from": self.node_id
                }
        elif method == "append_entries":
            # Handle AppendEntries RPC for log replication (Phase 3)
            payload = message.get("payload", {})
            leader_id = payload.get("leader_id")
            term = int(payload.get("term", 0))
            prev_log_index = int(payload.get("prev_log_index", 0))
            prev_log_term = int(payload.get("prev_log_term", 0))
            entries = payload.get("entries", []) or []
            leader_commit = int(payload.get("leader_commit", 0))

            if self.raft:
                resp = self.raft.handle_append_entries(
                    leader_id,
                    term,
                    prev_log_index,
                    prev_log_term,
                    entries,
                    leader_commit,
                )
                return {
                    "method": "append_entries_response",
                    "term": resp.get("term", term),
                    "success": bool(resp.get("success", False)),
                    "from": self.node_id,
                }
            else:
                return {
                    "method": "append_entries_response",
                    "term": term,
                    "success": True,
                    "from": self.node_id,
                }
        elif method == "leader_append":
            # Append a new payload on leader only (test/admin hook)
            payload = message.get("payload", {})
            if self.raft and getattr(self.raft.state, "value", "") == RaftState.LEADER.value:
                try:
                    self.raft.append_local(payload)
                    return {"method": "leader_append_response", "status": "ok", "from": self.node_id}
                except Exception as e:
                    return {"method": "leader_append_response", "status": "error", "error": str(e)}
            else:
                return {"method": "leader_append_response", "status": "not_leader", "from": self.node_id}
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

    async def request_vote(self, candidate_id: str, candidate_term: int, 
                         last_log_index: int = 0, last_log_term: int = 0) -> Dict[str, Any]:
        """Send RequestVote RPC to another node."""
        payload = {
            "candidate_id": candidate_id,
            "candidate_term": candidate_term,
            "last_log_index": last_log_index,
            "last_log_term": last_log_term
        }
        return await self.call("request_vote", payload)

    async def append_entries(self, leader_id: str, term: int, prev_log_index: int,
                           prev_log_term: int, entries: list, leader_commit: int) -> Dict[str, Any]:
        """Send AppendEntries RPC to another node (Phase 3)."""
        payload = {
            "leader_id": leader_id,
            "term": term,
            "prev_log_index": prev_log_index,
            "prev_log_term": prev_log_term,
            "entries": entries,
            "leader_commit": leader_commit
        }
        return await self.call("append_entries", payload)

    async def leader_append(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the node (if leader) to append a new payload to the Raft log."""
        return await self.call("leader_append", payload)
