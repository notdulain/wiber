#!/usr/bin/env python3
"""
Multi-Broker Startup Script

This script provides an easy way to start the multi-broker system
with different configurations.
"""

import asyncio
import subprocess
import sys
import os
import argparse
import time

def start_broker(node_id: str, port: int, peers: list):
    """Start a single broker instance"""
    cmd = [
        sys.executable, "-m", "src.api.multi_broker",
        "--node-id", node_id,
        "--port", str(port),
        "--peers", ",".join(peers)
    ]
    
    print(f"Starting {node_id} on port {port}...")
    process = subprocess.Popen(cmd)
    return process

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Start Multi-Broker Wiber Cluster')
    parser.add_argument('--brokers', type=int, default=3, help='Number of brokers to start (default: 3)')
    parser.add_argument('--start-port', type=int, default=8001, help='Starting port number (default: 8001)')
    parser.add_argument('--test', action='store_true', help='Run tests after starting brokers')
    
    args = parser.parse_args()
    
    if args.brokers < 1:
        print("❌ Number of brokers must be at least 1")
        return
    
    if args.brokers > 10:
        print("❌ Number of brokers cannot exceed 10")
        return
    
    print(f"🚀 Starting {args.brokers} broker cluster...")
    print(f"   Port range: {args.start_port} - {args.start_port + args.brokers - 1}")
    
    # Generate broker configuration
    brokers = []
    processes = []
    
    for i in range(args.brokers):
        node_id = f"broker-{i+1}"
        port = args.start_port + i
        peers = [f"broker-{j+1}" for j in range(args.brokers) if j != i]
        
        brokers.append((node_id, port, peers))
    
    try:
        # Start all brokers
        for node_id, port, peers in brokers:
            process = start_broker(node_id, port, peers)
            processes.append(process)
            time.sleep(2)  # Give each broker time to start
        
        print("✅ All brokers started successfully!")
        print("\n📊 Broker Information:")
        for i, (node_id, port, peers) in enumerate(brokers):
            print(f"   {node_id}: localhost:{port} (peers: {', '.join(peers)})")
        
        print(f"\n🔍 To check cluster status, run:")
        print(f"   python -c \"import asyncio; from src.api.client_discovery import ClientDiscovery; asyncio.run(ClientDiscovery([('localhost', {args.start_port}), ('localhost', {args.start_port + 1}), ('localhost', {args.start_port + 2})]).get_cluster_status())\"")
        
        print(f"\n📝 To publish messages, connect to the leader broker")
        print(f"   python -m src.producer.publisher chat 'Hello from multi-broker!'")
        
        print(f"\n📡 To subscribe to messages, connect to any broker")
        print(f"   python -m src.consumer.subscriber chat")
        
        if args.test:
            print(f"\n🧪 Running tests...")
            try:
                subprocess.run([sys.executable, "test_multi_broker.py"], check=True)
            except subprocess.CalledProcessError:
                print("❌ Tests failed")
            except FileNotFoundError:
                print("❌ Test script not found")
        
        print(f"\n⏳ Brokers are running... Press Ctrl+C to stop")
        
        # Wait for user interrupt
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n🛑 Stopping brokers...")
    
    except Exception as e:
        print(f"❌ Error starting brokers: {e}")
    
    finally:
        # Clean up processes
        for i, process in enumerate(processes):
            if process.poll() is None:  # Process is still running
                print(f"   Stopping broker-{i+1}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        print("✅ All brokers stopped")

if __name__ == "__main__":
    main()
