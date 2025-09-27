import asyncio
import json
import time
from typing import Dict, List, Optional, Tuple

class ClientDiscovery:
    """Client discovery service to find the current leader broker"""
    
    def __init__(self, brokers: List[Tuple[str, int]]):
        """
        Initialize client discovery service
        
        Args:
            brokers: List of (host, port) tuples for all brokers in the cluster
        """
        self.brokers = brokers
        self.current_leader: Optional[Tuple[str, int]] = None
        self.leader_cache_time = 0
        self.cache_duration = 30.0  # Cache leader info for 30 seconds
        
    async def find_leader(self) -> Optional[Tuple[str, int]]:
        """
        Find the current leader broker
        
        Returns:
            Tuple of (host, port) for the current leader, or None if no leader found
        """
        # Check cache first
        if (self.current_leader and 
            time.time() - self.leader_cache_time < self.cache_duration):
            return self.current_leader
        
        print("Discovering current leader...")
        
        # Query all brokers to find the leader
        for host, port in self.brokers:
            try:
                leader_info = await self._query_broker_status(host, port)
                if leader_info and leader_info.get("role") == "leader":
                    self.current_leader = (host, port)
                    self.leader_cache_time = time.time()
                    print(f"Found leader: {host}:{port}")
                    return self.current_leader
                    
            except Exception as e:
                print(f"Failed to query broker {host}:{port}: {e}")
                continue
        
        # No leader found
        print("No leader found in the cluster")
        return None
    
    async def _query_broker_status(self, host: str, port: int) -> Optional[Dict]:
        """
        Query a broker for its status
        
        Args:
            host: Broker hostname
            port: Broker port
            
        Returns:
            Status dictionary or None if query failed
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            
            try:
                # Read initial banner
                banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
                banner_str = banner.decode('utf-8').strip()
                print(f"Connected to {host}:{port} - {banner_str}")
                
                # Send STATUS command
                writer.write(b"STATUS\n")
                await writer.drain()
                
                # Read STATUS response
                response = await asyncio.wait_for(reader.readline(), timeout=5.0)
                response_str = response.decode('utf-8').strip()
                
                if response_str.startswith("STATUS "):
                    status_json = response_str[7:]  # Remove "STATUS " prefix
                    status = json.loads(status_json)
                    return status
                else:
                    print(f"Unexpected STATUS response from {host}:{port}: {response_str}")
                    return None
                    
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            print(f"Timeout querying broker {host}:{port}")
            return None
        except Exception as e:
            print(f"Error querying broker {host}:{port}: {e}")
            return None
    
    async def get_cluster_status(self) -> Dict:
        """
        Get status of all brokers in the cluster
        
        Returns:
            Dictionary with cluster status information
        """
        cluster_status = {
            "brokers": [],
            "leader": None,
            "total_brokers": len(self.brokers),
            "healthy_brokers": 0
        }
        
        for host, port in self.brokers:
            try:
                status = await self._query_broker_status(host, port)
                if status:
                    broker_info = {
                        "host": host,
                        "port": port,
                        "node_id": status.get("node_id"),
                        "role": status.get("role"),
                        "term": status.get("term"),
                        "log_length": status.get("log_length"),
                        "clients_connected": status.get("clients_connected"),
                        "healthy": True
                    }
                    cluster_status["brokers"].append(broker_info)
                    cluster_status["healthy_brokers"] += 1
                    
                    if status.get("role") == "leader":
                        cluster_status["leader"] = {
                            "host": host,
                            "port": port,
                            "node_id": status.get("node_id"),
                            "term": status.get("term")
                        }
                else:
                    # Broker is unhealthy
                    broker_info = {
                        "host": host,
                        "port": port,
                        "healthy": False
                    }
                    cluster_status["brokers"].append(broker_info)
                    
            except Exception as e:
                print(f"Error getting status from {host}:{port}: {e}")
                broker_info = {
                    "host": host,
                    "port": port,
                    "healthy": False,
                    "error": str(e)
                }
                cluster_status["brokers"].append(broker_info)
        
        return cluster_status
    
    async def wait_for_leader(self, timeout: float = 60.0) -> Optional[Tuple[str, int]]:
        """
        Wait for a leader to become available
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            Tuple of (host, port) for the current leader, or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            leader = await self.find_leader()
            if leader:
                return leader
            
            print("Waiting for leader to become available...")
            await asyncio.sleep(2.0)
        
        print(f"No leader found within {timeout} seconds")
        return None
    
    def clear_cache(self):
        """Clear the leader cache"""
        self.current_leader = None
        self.leader_cache_time = 0
        print("Leader cache cleared")

# Example usage and testing
async def test_discovery():
    """Test the client discovery service"""
    # Example broker list
    brokers = [
        ("localhost", 8001),
        ("localhost", 8002),
        ("localhost", 8003)
    ]
    
    discovery = ClientDiscovery(brokers)
    
    print("Testing client discovery...")
    
    # Find current leader
    leader = await discovery.find_leader()
    if leader:
        print(f"Current leader: {leader[0]}:{leader[1]}")
    else:
        print("No leader found")
    
    # Get cluster status
    cluster_status = await discovery.get_cluster_status()
    print(f"Cluster status: {json.dumps(cluster_status, indent=2)}")
    
    # Wait for leader
    leader = await discovery.wait_for_leader(timeout=10.0)
    if leader:
        print(f"Leader available: {leader[0]}:{leader[1]}")
    else:
        print("No leader available")

if __name__ == "__main__":
    asyncio.run(test_discovery())
