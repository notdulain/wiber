import argparse
import os
from confluent_kafka import Producer

def main():
    ap = argparse.ArgumentParser(description="Kafka Producer")
    ap.add_argument("topic")
    ap.add_argument("message")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    args = ap.parse_args()

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

    p.produce(args.topic, value=args.message.encode("utf-8"), on_delivery=on_delivery)
    p.flush(10)

if __name__ == "__main__":
    main()