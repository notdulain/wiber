"""Tests for RPC communication between nodes."""

import asyncio
import sys
from pathlib import Path

# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pytest

from cluster.rpc import RpcServer, RpcClient  # noqa: E402


@pytest.mark.asyncio
async def test_rpc_ping_pong(unused_tcp_port):
    """Test basic RPC ping/pong communication."""
    host = "127.0.0.1"
    port = unused_tcp_port
    
    # Start RPC server
    server = RpcServer(host, port, "test-server")
    await server.start()
    
    try:
        # Create client and ping server
        client = RpcClient(host, port, "test-client")
        response = await client.ping()
        
        # Verify response
        assert response["method"] == "pong"
        assert response["from"] == "test-server"
        assert "timestamp" in response
        
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rpc_unknown_method(unused_tcp_port):
    """Test RPC error handling for unknown methods."""
    host = "127.0.0.1"
    port = unused_tcp_port
    
    # Start RPC server
    server = RpcServer(host, port, "test-server")
    await server.start()
    
    try:
        # Create client and call unknown method
        client = RpcClient(host, port, "test-client")
        response = await client.call("unknown_method")
        
        # Verify error response
        assert response["method"] == "error"
        assert "Unknown method" in response["error"]
        
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rpc_connection_error():
    """Test RPC client handles connection errors gracefully."""
    client = RpcClient("127.0.0.1", 99999, "test-client")  # Non-existent port
    response = await client.ping()
    
    # Should return error response, not crash
    assert response["method"] == "error"
    assert "error" in response

