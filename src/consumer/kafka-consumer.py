import argparse
import os
from typing import List
from confluent_kafka import Consumer, TopicPartition

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

def main():
    ap = argparse.ArgumentParser(description="Kafka Consumer")
    ap.add_argument("topic")
    ap.add_argument("--from-beginning", action="store_true", help="Start consuming from earliest offset")
    ap.add_argument("--history", type=int, default=0, help="Fetch last N messages before tailing")
    ap.add_argument("--group", default="chat-consumers", help="Consumer group id")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    args = ap.parse_args()

    c = Consumer({
        "bootstrap.servers": args.bootstrap,
        "group.id": args.group,
        "auto.offset.reset": "earliest" if args.from_beginning else "latest",
        "enable.auto.commit": True,
    })

    try:
        if args.history > 0:
            # Use a temporary assignment to fetch tail N, outside of group subscription
            tail_history(c, args.topic, args.history)

        c.subscribe([args.topic])
        while True:
            msg = c.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("ERR:", msg.error())
                continue
            print(f"MSG {msg.topic()}[{msg.partition()}]@{msg.offset()} {msg.timestamp()} {msg.value().decode()}")
    except KeyboardInterrupt:
        pass
    finally:
        c.close()

if __name__ == "__main__":
    main()