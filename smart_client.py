#!/usr/bin/env python3
"""
Smart Client for Multi-Broker System

This script automatically discovers the current leader and connects to it.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.client_discovery import ClientDiscovery

async def find_leader_and_connect():
    """Find the current leader and return connection info"""
    brokers = [
        ("localhost", 8001),
        ("localhost", 8002),
        ("localhost", 8003)
    ]
    
    discovery = ClientDiscovery(brokers)
    leader = await discovery.find_leader()
    
    if leader:
        host, port = leader
        print(f"✅ Found leader: {host}:{port}")
        return host, port
    else:
        print("❌ No leader found in the cluster")
        return None, None

async def smart_publish(topic: str, message: str):
    """Publish message to the current leader"""
    host, port = await find_leader_and_connect()
    if not host or not port:
        print("❌ Cannot publish: no leader available")
        return
    
    try:
        reader, writer = await asyncio.open_connection(host, port)
        # Drain initial banner
        await reader.readline()
        
        # Publish message
        writer.write(f"PUB {topic} {message}\n".encode("utf-8"))
        await writer.drain()
        
        response = await reader.readline()
        print(f"📝 Published: {response.decode().strip()}")
        
        # Close connection
        writer.write(b"QUIT\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        print(f"❌ Error publishing: {e}")

async def smart_subscribe(topic: str, group_id: str = None, history: int = 0):
    """Subscribe to messages from the current leader"""
    host, port = await find_leader_and_connect()
    if not host or not port:
        print("❌ Cannot subscribe: no leader available")
        return
    
    try:
        reader, writer = await asyncio.open_connection(host, port)
        banner = await reader.readline()
        print(f"🔗 Connected: {banner.decode().strip()}")
        
        # Subscribe to topic
        if group_id:
            writer.write(f"SUB {topic} {group_id}\n".encode("utf-8"))
            print(f"📡 Subscribing to topic '{topic}' in group '{group_id}'")
        else:
            writer.write(f"SUB {topic}\n".encode("utf-8"))
            print(f"📡 Subscribing to topic '{topic}' (no group)")
        
        await writer.drain()
        response = await reader.readline()
        print(f"✅ Subscription: {response.decode().strip()}")
        
        # Request history if needed
        if history > 0:
            writer.write(f"HISTORY {topic} {history}\n".encode("utf-8"))
            await writer.drain()
        
        # Start heartbeat for consumer groups
        heartbeat_task = None
        if group_id:
            async def heartbeat_loop():
                while True:
                    await asyncio.sleep(10.0)
                    try:
                        writer.write(b"HEARTBEAT\n")
                        await writer.drain()
                        print("💓 Heartbeat sent")
                    except Exception as e:
                        print(f"❌ Heartbeat failed: {e}")
                        break
            
            heartbeat_task = asyncio.create_task(heartbeat_loop())
            print("💓 Started heartbeat monitoring")
        
        # Read messages
        print("📨 Listening for messages...")
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                
                message = line.decode().strip()
                print(f"📨 {message}")
                
                # Handle ACK for consumer groups
                if group_id and message.startswith("MSG "):
                    parts = message.split(maxsplit=5)
                    if len(parts) >= 3:
                        message_id = parts[2]
                        print(f"⚙️  Processing message {message_id}...")
                        await asyncio.sleep(0.1)  # Simulate processing
                        
                        # Send ACK
                        writer.write(f"ACK {message_id}\n".encode("utf-8"))
                        await writer.drain()
                        
                        ack_response = await reader.readline()
                        print(f"✅ ACK: {ack_response.decode().strip()}")
                        
        except KeyboardInterrupt:
            print("\n🛑 Stopping subscriber...")
        finally:
            # Cleanup
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            try:
                writer.write(b"QUIT\n")
                await writer.drain()
            except Exception:
                pass
            writer.close()
            await writer.wait_closed()
            
    except Exception as e:
        print(f"❌ Error subscribing: {e}")

async def check_cluster_status():
    """Check the status of the multi-broker cluster"""
    brokers = [
        ("localhost", 8001),
        ("localhost", 8002),
        ("localhost", 8003)
    ]
    
    discovery = ClientDiscovery(brokers)
    status = await discovery.get_cluster_status()
    
    print("📊 Cluster Status:")
    print(f"   Total brokers: {status['total_brokers']}")
    print(f"   Healthy brokers: {status['healthy_brokers']}")
    
    if status['leader']:
        leader = status['leader']
        print(f"   ✅ Leader: {leader['node_id']} ({leader['host']}:{leader['port']}) - Term {leader['term']}")
    else:
        print("   ❌ Leader: None")
    
    print("   Broker details:")
    for broker in status['brokers']:
        if broker['healthy']:
            print(f"     ✅ {broker['node_id']} ({broker['host']}:{broker['port']}) - {broker['role']} - Term {broker['term']}")
        else:
            print(f"     ❌ {broker['host']}:{broker['port']} - Unhealthy")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Client for Multi-Broker System')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Publish command
    pub_parser = subparsers.add_parser('publish', help='Publish a message')
    pub_parser.add_argument('topic', help='Topic to publish to')
    pub_parser.add_argument('message', help='Message content')
    
    # Subscribe command
    sub_parser = subparsers.add_parser('subscribe', help='Subscribe to messages')
    sub_parser.add_argument('topic', help='Topic to subscribe to')
    sub_parser.add_argument('--group', help='Consumer group ID')
    sub_parser.add_argument('--history', type=int, default=0, help='Fetch last N messages')
    
    # Status command
    subparsers.add_parser('status', help='Check cluster status')
    
    args = parser.parse_args()
    
    if args.command == 'publish':
        asyncio.run(smart_publish(args.topic, args.message))
    elif args.command == 'subscribe':
        asyncio.run(smart_subscribe(args.topic, args.group, args.history))
    elif args.command == 'status':
        asyncio.run(check_cluster_status())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
