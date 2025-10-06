import socket
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TimeSyncConfig:
    """Configuration for time synchronization."""
    sync_interval: float = 30.0  # seconds
    max_skew_threshold: float = 100.0  # milliseconds
    sample_size: int = 3  # number of samples for offset calculation
    timeout: float = 5.0  # socket timeout in seconds


class TimeSyncMessage:
    """Time synchronization message format."""
    
    @staticmethod
    def create_sync_request() -> Dict:
        """Create a time sync request message."""
        return {
            "type": "sync_request",
            "t1": time.time(),  # client send time
            "timestamp": time.time()
        }
    
    @staticmethod
    def create_sync_response(request: Dict) -> Dict:
        """Create a time sync response message."""
        return {
            "type": "sync_response",
            "t1": request["t1"],  # original client send time
            "t2": time.time(),    # server receive time
            "t3": time.time(),    # server send time
            "timestamp": time.time()
        }
    
    @staticmethod
    def calculate_offset(response: Dict, t4: float) -> Tuple[float, float]:
        """Calculate clock offset from sync response. Returns (offset, delay)."""
        t1, t2, t3 = response["t1"], response["t2"], response["t3"]
        delay = (t4 - t1) - (t3 - t2)
        offset = ((t2 - t1) + (t3 - t4)) / 2
        return offset, delay


class TimeSyncClient:
    """Client for time synchronization with other nodes."""
    
    def __init__(self, node_id: str, config: TimeSyncConfig = None):
        self.node_id = node_id
        self.config = config or TimeSyncConfig()
        self.offsets: Dict[str, float] = {}  # peer_id -> offset
        self.last_sync: Dict[str, float] = {}  # peer_id -> last sync time
        self.running = False
        self.sync_thread = None
    
    def measure_offset(self, peer_host: str, peer_port: int, peer_id: str = None) -> Optional[float]:
        """Measure clock offset to a peer using SNTP-style protocol."""
        if peer_id is None:
            peer_id = f"{peer_host}:{peer_port}"
        
        try:
            # Create sync request
            request = TimeSyncMessage.create_sync_request()
            t1 = request["t1"]
            
            # Send request and receive response
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.config.timeout)
                sock.connect((peer_host, peer_port))
                
                # Send request
                message = f"TIME_SYNC {request['t1']}\n"
                sock.sendall(message.encode())
                
                # Receive a full line response
                try:
                    f = sock.makefile('r')
                    response_data = f.readline().strip()
                finally:
                    try:
                        f.close()
                    except Exception:
                        pass
                t4 = time.time()
                
                # Parse response (format: "TIME_SYNC_RESPONSE t1 t2 t3")
                parts = response_data.split()
                if len(parts) >= 4 and parts[0] == "TIME_SYNC_RESPONSE":
                    t1_recv, t2, t3 = float(parts[1]), float(parts[2]), float(parts[3])
                    
                    # Calculate offset
                    offset, delay = TimeSyncMessage.calculate_offset({
                        "t1": t1_recv, "t2": t2, "t3": t3
                    }, t4)
                    
                    # Store offset
                    self.offsets[peer_id] = offset
                    self.last_sync[peer_id] = time.time()
                    
                    return offset
                    
        except Exception as e:
            print(f"Time sync failed with {peer_id}: {e}")
            return None
        
        return None
    
    def get_average_offset(self) -> float:
        """Get average offset across all peers."""
        if not self.offsets:
            return 0.0
        
        valid_offsets = [offset for offset in self.offsets.values() if offset is not None]
        if not valid_offsets:
            return 0.0
        
        return sum(valid_offsets) / len(valid_offsets)
    
    def get_synchronized_time(self) -> float:
        """Return local time corrected by average offset."""
        return time.time() + self.get_average_offset()
    
    def start_sync(self, peers: List[Tuple[str, int, str]]) -> None:
        """Start background synchronization to a list of peers."""
        if self.running:
            return
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, args=(peers,), daemon=True)
        self.sync_thread.start()
    
    def stop_sync(self) -> None:
        """Stop background synchronization."""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join()
    
    def _sync_loop(self, peers: List[Tuple[str, int, str]]):
        """Background synchronization loop."""
        while self.running:
            try:
                for peer_host, peer_port, peer_id in peers:
                    if not self.running:
                        break
                    
                    self.measure_offset(peer_host, peer_port, peer_id)
                    time.sleep(1)  # Small delay between peers
                
                time.sleep(self.config.sync_interval)
                
            except Exception as e:
                print(f"Background sync error: {e}")
                time.sleep(5)


class TimeSyncServer:
    """Server for handling time synchronization requests."""
    
    def __init__(self, node_id: str, host: str = "0.0.0.0", port: int = 9100):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.server_thread = None
    
    def start(self):
        """Start the time sync server."""
        if self.running:
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        print(f"Time sync server started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop the time sync server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.server_thread:
            self.server_thread.join()
    
    def _server_loop(self):
        """Main server loop."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    threading.Thread(
                        target=self._handle_client, 
                        args=(client_socket, addr), 
                        daemon=True
                    ).start()
                except socket.error:
                    if self.running:
                        print("Server socket error")
                    break
                    
        except Exception as e:
            print(f"Time sync server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def _handle_client(self, client_socket: socket.socket, addr: Tuple[str, int]):
        """Handle time sync request from client."""
        try:
            data = client_socket.recv(1024).decode().strip()
            
            if data.startswith("TIME_SYNC "):
                # Parse request
                t1 = float(data.split()[1])
                t2 = time.time()  # server receive time
                t3 = time.time()  # server send time
                
                # Send response
                response = f"TIME_SYNC_RESPONSE {t1} {t2} {t3}\n"
                client_socket.sendall(response.encode())
                
        except Exception as e:
            print(f"Error handling time sync request from {addr}: {e}")
        finally:
            client_socket.close()


class BoundedReordering:
    """Bounded reordering system for message ordering."""
    
    def __init__(self, max_delay_ms: float = 100.0):
        self.max_delay_ms = max_delay_ms
        self.pending_messages: List[Dict] = []
        self.lock = threading.Lock()
    
    def add_message(self, message: Dict) -> List[Dict]:
        """Add message and return any messages ready for delivery."""
        with self.lock:
            self.pending_messages.append(message)
            
            # Sort by timestamp
            self.pending_messages.sort(key=lambda m: m.get("timestamp", 0))
            
            # Check for messages ready for delivery
            ready_messages = []
            current_time = time.time()
            
            for msg in self.pending_messages[:]:
                msg_time = msg.get("timestamp", 0)
                delay = (current_time - msg_time) * 1000  # Convert to ms
                
                if delay >= self.max_delay_ms:
                    ready_messages.append(msg)
                    self.pending_messages.remove(msg)
            
            return ready_messages
    
    def get_pending_count(self) -> int:
        """Get number of pending messages."""
        with self.lock:
            return len(self.pending_messages)


# Legacy function for backward compatibility
def measure_offset(peer_host: str, peer_port: int) -> float:
    """Estimate clock offset to a peer (legacy function)."""
    client = TimeSyncClient("legacy")
    offset = client.measure_offset(peer_host, peer_port)
    return offset if offset is not None else 0.0
