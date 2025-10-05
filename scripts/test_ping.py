#!/usr/bin/env python3
"""Simple PING test client for the Wiber API server."""

import asyncio
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


async def test_ping(host: str = "127.0.0.1", port: int = 9101):
    """Test PING command against the API server."""
    try:
        reader, writer = await asyncio.open_connection(host, port)
        
        # Send PING
        writer.write(b"PING\n")
        await writer.drain()
        
        # Read response
        response = await reader.readline()
        response_str = response.decode("utf-8").strip()
        
        writer.close()
        await writer.wait_closed()
        
        print(f"Sent: PING")
        print(f"Received: {response_str}")
        
        if response_str == "PONG":
            print("✅ PING test passed!")
            return True
        else:
            print("❌ PING test failed!")
            return False
            
    except ConnectionRefusedError:
        print(f"❌ Could not connect to {host}:{port}")
        print("Make sure the node is running with: python scripts\\run_cluster.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run the PING test."""
    print("Testing PING against Wiber API server...")
    success = asyncio.run(test_ping())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
