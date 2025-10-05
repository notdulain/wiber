#!/usr/bin/env python3
"""Interactive Wiber Client - Type commands manually"""

import socket
import json

class InteractiveWiberClient:
    def __init__(self, host="127.0.0.1", port=9101):
        self.host = host
        self.port = port
        self.client = None
    
    def connect(self):
        """Connect to Wiber server."""
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.host, self.port))
            print(f"OK Connected to Wiber at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"ERROR Connection failed: {e}")
            print("Make sure the cluster is running: python scripts\\run_cluster.py")
            return False
    
    def send_command(self, command):
        """Send a command and get response."""
        try:
            # Create a new connection for each command
            temp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_client.connect((self.host, self.port))
            
            temp_client.send(command.encode('utf-8') + b'\n')
            response = temp_client.recv(4096).decode('utf-8').strip()
            
            temp_client.close()
            return response
        except Exception as e:
            print(f"ERROR Command failed: {e}")
            return None
    
    def close(self):
        """Close connection."""
        if self.client:
            self.client.close()
            print("Disconnected Disconnected from Wiber")

def main():
    """Interactive command-line client."""
    print("Wiber Wiber Interactive Client")
    print("=" * 40)
    print("Commands:")
    print("  PING                    - Test connection")
    print("  PUB <topic> <message>   - Send message")
    print("  SUB <topic>             - Subscribe to topic")
    print("  HISTORY <topic> [limit] - Get message history")
    print("  TOPICS                  - List available topics")
    print("  STATS [topic]           - Show statistics")
    print("  HELP                    - Show help")
    print("  QUIT                    - Exit")
    print("=" * 40)
    
    # Create client
    client = InteractiveWiberClient()
    
    # Connect
    if not client.connect():
        return
    
    # Interactive loop
    while True:
        try:
            # Get user input
            command = input("\nwiber> ").strip()
            
            if not command:
                continue
            
            if command.upper() == "QUIT":
                break
            
            # Send command
            response = client.send_command(command)
            
            if response:
                print(f"Response: {response}")
                
                # Pretty print JSON responses
                if response.startswith("OK") and len(response) > 3:
                    json_part = response[3:]  # Remove "OK "
                    try:
                        data = json.loads(json_part)
                        
                        # Handle HISTORY command
                        if isinstance(data, dict) and 'messages' in data:
                            print(f"\n📚 {data['count']} messages in '{data['topic']}':")
                            for msg in data['messages']:
                                content = msg['message']['content']
                                offset = msg['offset']
                                print(f"  [{offset}] {content}")
                        
                        # Handle TOPICS command
                        elif isinstance(data, dict) and 'topics' in data:
                            print(f"\n📋 Available Topics ({data['count']}):")
                            for topic in data['topics']:
                                name = topic['name']
                                desc = topic.get('description', 'No description')
                                retention = topic.get('retention_hours', 0)
                                max_msgs = topic.get('max_messages', 0)
                                print(f"  • {name}")
                                print(f"    Description: {desc}")
                                if retention > 0:
                                    print(f"    Retention: {retention} hours")
                                if max_msgs > 0:
                                    print(f"    Max Messages: {max_msgs}")
                                print()
                        
                        # Handle STATS command
                        elif isinstance(data, dict) and ('topic' in data or 'cluster' in data):
                            if 'topic' in data:
                                # Topic-specific stats
                                topic = data['topic']
                                print(f"\n📊 Statistics for '{topic}':")
                                print(f"  Messages: {data.get('message_count', 0)}")
                                print(f"  Latest Offset: {data.get('latest_offset', -1)}")
                                print(f"  Subscribers: {data.get('subscriber_count', 0)}")
                                print(f"  Deduplication: {'Enabled' if data.get('deduplication_enabled', False) else 'Disabled'}")
                                retention = data.get('retention_hours', 0)
                                if retention > 0:
                                    print(f"  Retention: {retention} hours")
                                max_msgs = data.get('max_messages', 0)
                                if max_msgs > 0:
                                    print(f"  Max Messages: {max_msgs}")
                            else:
                                # Cluster stats
                                cluster = data['cluster']
                                print(f"\n📊 Cluster Statistics:")
                                print(f"  Total Topics: {cluster.get('total_topics', 0)}")
                                print(f"  Total Messages: {cluster.get('total_messages', 0)}")
                                print(f"  Total Subscribers: {cluster.get('total_subscribers', 0)}")
                        
                        # Handle HELP command
                        elif isinstance(data, dict) and 'commands' in data:
                            print(f"\n❓ Available Commands:")
                            for cmd in data['commands']:
                                command = cmd['command']
                                description = cmd['description']
                                usage = cmd['usage']
                                print(f"  {command:<10} - {description}")
                                print(f"    Usage: {usage}")
                                print()
                        
                    except json.JSONDecodeError:
                        pass  # Not JSON, just print as is
            else:
                print("No response received")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    # Close
    client.close()
    print("Goodbye Goodbye!")

if __name__ == "__main__":
    main()
