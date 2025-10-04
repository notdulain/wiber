import argparse
import os
import json
import uuid
from confluent_kafka import Producer
from src.utils.time_sync import get_time_sync, TimeSyncConfig, ClockType, simulate_clock_skew

def main():
    ap = argparse.ArgumentParser(description="Kafka Producer with Time Synchronization")
    ap.add_argument("topic")
    ap.add_argument("message")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    ap.add_argument("--node-id", default="producer-1", help="Node identifier for time sync")
    ap.add_argument("--clock-type", choices=["physical", "logical", "vector"], 
                   default="physical", help="Type of clock to use")
    ap.add_argument("--enable-ntp", action="store_true", help="Enable NTP synchronization")
    ap.add_argument("--simulate-skew", type=float, default=0, 
                   help="Simulate clock skew in milliseconds")
    ap.add_argument("--simulate-drift", type=float, default=0,
                   help="Simulate clock drift in ms per second")
    ap.add_argument("--random-variation", type=int, default=0,
                   help="Random time variation in milliseconds")
    args = ap.parse_args()

    # Configure time synchronization
    config = TimeSyncConfig(
        ntp_servers=["pool.ntp.org", "time.google.com"] if args.enable_ntp else None,
        logical_clock_enabled=args.clock_type == "logical",
        vector_clock_enabled=args.clock_type == "vector"
    )
    
    time_sync = get_time_sync(config, args.node_id)
    
    if args.enable_ntp:
        time_sync.start_sync()
        print("NTP synchronization enabled")

    p = Producer({
        "bootstrap.servers": args.bootstrap,
        "enable.idempotence": True,
        "acks": "all",
        "retries": 3,
        "linger.ms": 5,
    })

    def on_delivery(err, msg):
        if err:
            print(f"ERR: {err}")
        else:
            print(f"OK published to {msg.topic()}@{msg.partition()} offset {msg.offset()}")

    # Create message with time synchronization
    message_data = {
        "id": str(uuid.uuid4()),
        "content": args.message,
        "timestamp": time_sync.create_timestamp(ClockType(args.clock_type))
    }
    
    # Add simulated skew if specified
    if args.simulate_skew != 0 or args.simulate_drift != 0 or args.random_variation != 0:
        skew = simulate_clock_skew(args.simulate_skew, args.simulate_drift, args.random_variation)
        message_data["simulated_skew_ms"] = skew
        message_data["timestamp"]["simulated_time"] = message_data["timestamp"]["timestamp"] + (skew / 1000.0)

    # Serialize message
    message_json = json.dumps(message_data, indent=2)
    
    print(f"Publishing message with {args.clock_type} clock:")
    print(message_json)
    
    p.produce(args.topic, value=message_json.encode("utf-8"), on_delivery=on_delivery)
    p.flush(10)
    
    if args.enable_ntp:
        time_sync.stop_sync()

if __name__ == "__main__":
    main()