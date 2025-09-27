#!/usr/bin/env python3
"""
Multi-Broker Test Script

This script demonstrates the multi-broker architecture with:
1. Starting multiple broker instances
2. Leader election
3. Message publishing and consumption
4. Failure scenarios
"""

import asyncio
import subprocess
import time
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.client_discovery import ClientDiscovery

class MultiBrokerTester:
    """Test the multi-broker system"""
    
    def __init__(self):
        self.brokers = [
            ("localhost", 8001),
            ("localhost", 8002),
            ("localhost", 8003)
        ]
        self.discovery = ClientDiscovery(self.brokers)
        self.broker_processes = []
        
    async def start_brokers(self):
        """Start all broker instances"""
        print("🚀 Starting multi-broker cluster...")
        
        for i, (host, port) in enumerate(self.brokers):
            node_id = f"broker-{i+1}"
            peers = ",".join([f"broker-{j+1}" for j in range(len(self.brokers)) if j != i])
            
            cmd = [
                sys.executable, "-m", "src.api.multi_broker",
                "--node-id", node_id,
                "--port", str(port),
                "--peers", peers
            ]
            
            print(f"Starting {node_id} on port {port}...")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.broker_processes.append(process)
            
            # Give broker time to start
            await asyncio.sleep(2.0)
        
        print("✅ All brokers started")
    
    async def wait_for_leader(self, timeout: float = 30.0):
        """Wait for a leader to be elected"""
        print("⏳ Waiting for leader election...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            leader = await self.discovery.find_leader()
            if leader:
                print(f"✅ Leader elected: {leader[0]}:{leader[1]}")
                return leader
            
            print("Still waiting for leader...")
            await asyncio.sleep(2.0)
        
        print("❌ No leader elected within timeout")
        return None
    
    async def get_cluster_status(self):
        """Get current cluster status"""
        print("📊 Getting cluster status...")
        
        status = await self.discovery.get_cluster_status()
        print(f"Cluster Status:")
        print(f"  Total brokers: {status['total_brokers']}")
        print(f"  Healthy brokers: {status['healthy_brokers']}")
        
        if status['leader']:
            leader = status['leader']
            print(f"  Leader: {leader['node_id']} ({leader['host']}:{leader['port']}) - Term {leader['term']}")
        else:
            print("  Leader: None")
        
        print("  Broker details:")
        for broker in status['brokers']:
            if broker['healthy']:
                print(f"    ✅ {broker['node_id']} ({broker['host']}:{broker['port']}) - {broker['role']} - Term {broker['term']}")
            else:
                print(f"    ❌ {broker['host']}:{broker['port']} - Unhealthy")
        
        return status
    
    async def test_message_publishing(self):
        """Test message publishing to the leader"""
        print("📝 Testing message publishing...")
        
        leader = await self.discovery.find_leader()
        if not leader:
            print("❌ No leader available for publishing")
            return
        
        host, port = leader
        
        try:
            reader, writer = await asyncio.open_connection(host, port)
            
            # Test publishing
            test_messages = [
                "Hello from multi-broker!",
                "This is a test message",
                "Multi-broker architecture working!"
            ]
            
            for i, message in enumerate(test_messages):
                pub_command = f"PUB chat {message}\n"
                writer.write(pub_command.encode())
                await writer.drain()
                
                response = await reader.readline()
                response_str = response.decode().strip()
                print(f"  Published: {message} -> {response_str}")
                
                await asyncio.sleep(1.0)
            
            writer.close()
            await writer.wait_closed()
            print("✅ Message publishing test completed")
            
        except Exception as e:
            print(f"❌ Error during message publishing: {e}")
    
    async def test_subscription(self):
        """Test message subscription"""
        print("📡 Testing message subscription...")
        
        leader = await self.discovery.find_leader()
        if not leader:
            print("❌ No leader available for subscription")
            return
        
        host, port = leader
        
        try:
            reader, writer = await asyncio.open_connection(host, port)
            
            # Subscribe to chat topic
            sub_command = "SUB chat\n"
            writer.write(sub_command.encode())
            await writer.drain()
            
            response = await reader.readline()
            print(f"  Subscription: {response.decode().strip()}")
            
            # Wait for messages
            print("  Waiting for messages...")
            try:
                while True:
                    response = await asyncio.wait_for(reader.readline(), timeout=5.0)
                    if not response:
                        break
                    
                    response_str = response.decode().strip()
                    if response_str.startswith("MSG "):
                        print(f"  Received: {response_str}")
                    elif response_str.startswith("OK "):
                        print(f"  Response: {response_str}")
                    else:
                        print(f"  Other: {response_str}")
                        
            except asyncio.TimeoutError:
                print("  No more messages received")
            
            writer.close()
            await writer.wait_closed()
            print("✅ Message subscription test completed")
            
        except Exception as e:
            print(f"❌ Error during message subscription: {e}")
    
    async def test_leader_failover(self):
        """Test leader failover by killing the current leader"""
        print("💥 Testing leader failover...")
        
        # Get current leader
        leader = await self.discovery.find_leader()
        if not leader:
            print("❌ No leader available for failover test")
            return
        
        host, port = leader
        leader_index = None
        
        # Find which broker process is the leader
        for i, (h, p) in enumerate(self.brokers):
            if h == host and p == port:
                leader_index = i
                break
        
        if leader_index is None:
            print("❌ Could not identify leader process")
            return
        
        print(f"  Killing leader broker-{leader_index + 1} ({host}:{port})...")
        
        # Kill the leader process
        process = self.broker_processes[leader_index]
        process.terminate()
        process.wait()
        
        print("  Waiting for new leader election...")
        await asyncio.sleep(5.0)
        
        # Wait for new leader
        new_leader = await self.wait_for_leader(timeout=20.0)
        if new_leader:
            print(f"✅ New leader elected: {new_leader[0]}:{new_leader[1]}")
            
            # Test that new leader can accept publishes
            await self.test_message_publishing()
        else:
            print("❌ No new leader elected after failover")
    
    async def run_tests(self):
        """Run all tests"""
        print("🧪 Starting Multi-Broker Tests")
        print("=" * 50)
        
        try:
            # Start brokers
            await self.start_brokers()
            
            # Wait for leader election
            leader = await self.wait_for_leader()
            if not leader:
                print("❌ Failed to elect a leader")
                return
            
            # Get cluster status
            await self.get_cluster_status()
            
            # Test message publishing
            await self.test_message_publishing()
            
            # Test message subscription
            await self.test_subscription()
            
            # Test leader failover
            await self.test_leader_failover()
            
            print("=" * 50)
            print("✅ All tests completed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Clean up
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up broker processes"""
        print("🧹 Cleaning up...")
        
        for i, process in enumerate(self.broker_processes):
            if process.poll() is None:  # Process is still running
                print(f"  Stopping broker-{i+1}...")
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        print("✅ Cleanup completed")

async def main():
    """Main function"""
    tester = MultiBrokerTester()
    await tester.run_tests()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
