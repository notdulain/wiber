import argparse
import os
import json
from typing import List, Dict, Any
from confluent_kafka import Consumer, TopicPartition
from src.utils.time_sync import get_time_sync, TimeSyncConfig, ClockType

def tail_history(c: Consumer, topic: str, n: int):
    """Read last N messages across all partitions, then return."""
    md = c.list_topics(topic=topic, timeout=10)
    parts = sorted(md.topics[topic].partitions.keys())
    tps: List[TopicPartition] = []
    # Compute start offsets per partition from watermarks
    for p in parts:
        tp = TopicPartition(topic, p)
        lo, hi = c.get_watermark_offsets(tp, cached=False)
        start = max(lo, hi - n)
        tps.append(TopicPartition(topic, p, start))
    c.assign(tps)
    read = 0
    while read < n:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print("ERR:", msg.error())
            continue
        print(f"HISTORY {msg.topic()}[{msg.partition()}]@{msg.offset()} {msg.timestamp()} {msg.value().decode()}")
        read += 1
    c.unassign()

def parse_time_sync_message(msg_value: str) -> Dict[str, Any]:
    """Parse message and extract time synchronization information"""
    try:
        data = json.loads(msg_value)
        return data
    except json.JSONDecodeError:
        # Fallback for non-JSON messages
        return {"content": msg_value, "timestamp": None}

def format_timestamp_info(timestamp_data: Dict) -> str:
    """Format timestamp information for display"""
    if not timestamp_data:
        return "No timestamp"
    
    info_parts = []
    
    if "physical_time" in timestamp_data:
        info_parts.append(f"physical={timestamp_data['physical_time']:.3f}")
    
    if "logical_time" in timestamp_data:
        info_parts.append(f"logical={timestamp_data['logical_time']}")
    
    if "vector_time" in timestamp_data:
        info_parts.append(f"vector={timestamp_data['vector_time']}")
    
    if "simulated_time" in timestamp_data:
        info_parts.append(f"simulated={timestamp_data['simulated_time']:.3f}")
    
    return f"[{', '.join(info_parts)}]"

def analyze_message_ordering(messages: List[Dict]) -> None:
    """Analyze message ordering based on different clock types"""
    if len(messages) < 2:
        return
    
    print("\n=== MESSAGE ORDERING ANALYSIS ===")
    
    # Sort by Kafka offset (broker order)
    offset_ordered = sorted(messages, key=lambda m: m.get('kafka_offset', 0))
    print("Broker order (by offset):")
    for i, msg in enumerate(offset_ordered):
        print(f"  {i+1}. Offset {msg.get('kafka_offset', 'N/A')}: {msg.get('content', 'N/A')[:50]}...")
    
    # Sort by physical time if available
    physical_times = [m for m in messages if m.get('timestamp', {}).get('physical_time')]
    if len(physical_times) >= 2:
        physical_ordered = sorted(physical_times, key=lambda m: m['timestamp']['physical_time'])
        print("\nPhysical time order:")
        for i, msg in enumerate(physical_ordered):
            pt = msg['timestamp']['physical_time']
            print(f"  {i+1}. Time {pt:.3f}: {msg.get('content', 'N/A')[:50]}...")
    
    # Sort by logical time if available
    logical_times = [m for m in messages if m.get('timestamp', {}).get('logical_time')]
    if len(logical_times) >= 2:
        logical_ordered = sorted(logical_times, key=lambda m: m['timestamp']['logical_time'])
        print("\nLogical time order:")
        for i, msg in enumerate(logical_ordered):
            lt = msg['timestamp']['logical_time']
            print(f"  {i+1}. Logical {lt}: {msg.get('content', 'N/A')[:50]}...")
    
    print("=" * 40)

def main():
    ap = argparse.ArgumentParser(description="Kafka Consumer with Time Synchronization Analysis")
    ap.add_argument("topic")
    ap.add_argument("--from-beginning", action="store_true", help="Start consuming from earliest offset")
    ap.add_argument("--history", type=int, default=0, help="Fetch last N messages before tailing")
    ap.add_argument("--group", default="chat-consumers", help="Consumer group id")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    ap.add_argument("--node-id", default="consumer-1", help="Node identifier for time sync")
    ap.add_argument("--enable-ntp", action="store_true", help="Enable NTP synchronization")
    ap.add_argument("--analyze-ordering", action="store_true", help="Analyze message ordering")
    ap.add_argument("--buffer-size", type=int, default=10, help="Number of messages to buffer for analysis")
    args = ap.parse_args()

    # Configure time synchronization
    config = TimeSyncConfig(
        ntp_servers=["pool.ntp.org", "time.google.com"] if args.enable_ntp else None,
        logical_clock_enabled=True,
        vector_clock_enabled=False
    )
    
    time_sync = get_time_sync(config, args.node_id)
    
    if args.enable_ntp:
        time_sync.start_sync()
        print("NTP synchronization enabled")

    c = Consumer({
        "bootstrap.servers": args.bootstrap,
        "group.id": args.group,
        "auto.offset.reset": "earliest" if args.from_beginning else "latest",
        "enable.auto.commit": True,
    })

    message_buffer = []

    try:
        if args.history > 0:
            # Use a temporary assignment to fetch tail N, outside of group subscription
            tail_history(c, args.topic, args.history)

        c.subscribe([args.topic])
        print(f"Consuming from topic '{args.topic}' with time sync analysis...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            msg = c.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("ERR:", msg.error())
                continue
            
            # Parse message
            message_data = parse_time_sync_message(msg.value().decode())
            message_data['kafka_offset'] = msg.offset()
            message_data['kafka_partition'] = msg.partition()
            message_data['kafka_timestamp'] = msg.timestamp()
            
            # Update time sync if message has timestamp
            if message_data.get('timestamp'):
                time_sync.update_from_message(message_data['timestamp'])
            
            # Display message
            timestamp_info = format_timestamp_info(message_data.get('timestamp', {}))
            content = message_data.get('content', 'N/A')
            
            print(f"MSG {msg.topic()}[{msg.partition()}]@{msg.offset()} {timestamp_info}")
            print(f"  Content: {content}")
            
            if message_data.get('simulated_skew_ms'):
                print(f"  Simulated skew: {message_data['simulated_skew_ms']:.2f}ms")
            
            print()
            
            # Buffer for ordering analysis
            if args.analyze_ordering:
                message_buffer.append(message_data)
                if len(message_buffer) > args.buffer_size:
                    message_buffer.pop(0)
                
                if len(message_buffer) >= 2:
                    analyze_message_ordering(message_buffer)
            
    except KeyboardInterrupt:
        print("\nStopping consumer...")
    finally:
        if args.enable_ntp:
            time_sync.stop_sync()
        c.close()

if __name__ == "__main__":
    main()