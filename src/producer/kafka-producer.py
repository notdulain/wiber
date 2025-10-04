import argparse
import os
from confluent_kafka import Producer

def main():
    ap = argparse.ArgumentParser(description="Kafka Producer")
    ap.add_argument("topic")
    ap.add_argument("message")
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    ap.add_argument("--key", default=os.getenv("KAFKA_KEY"))
    ap.add_argument("--acks", default=os.getenv("KAFKA_ACKS", "all"))
    ap.add_argument("--retries", type=int, default=int(os.getenv("KAFKA_RETRIES", "10")))
    ap.add_argument("--linger-ms", dest="linger_ms", type=int, default=int(os.getenv("KAFKA_LINGER_MS", "5")))
    ap.add_argument("--request-timeout-ms", type=int, default=int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000")))
    ap.add_argument("--delivery-timeout-ms", type=int, default=int(os.getenv("KAFKA_DELIVERY_TIMEOUT_MS", "120000")))
    ap.add_argument("--retry-backoff-ms", type=int, default=int(os.getenv("KAFKA_RETRY_BACKOFF_MS", "100")))
    ap.add_argument("--max-in-flight", type=int, default=int(os.getenv("KAFKA_MAX_IN_FLIGHT", "5")))
    ap.add_argument("--flush-timeout-s", type=int, default=int(os.getenv("KAFKA_FLUSH_TIMEOUT_S", "10")))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg = {
        "bootstrap.servers": args.bootstrap,
        "enable.idempotence": True,
        "acks": args.acks,
        "retries": args.retries,
        "linger.ms": args.linger_ms,
        "request.timeout.ms": args.request_timeout_ms,
        "delivery.timeout.ms": args.delivery_timeout_ms,
        "retry.backoff.ms": args.retry_backoff_ms,
        "max.in.flight.requests.per.connection": args.max_in_flight,
    }
    if args.verbose:
        print(f"Producer config: {cfg}")
    p = Producer(cfg)

    def on_delivery(err, msg):
        if err:
            print(f"ERR: {err}")
        else:
            print(f"OK published to {msg.topic()}@{msg.partition()} offset {msg.offset()}")

    try:
        p.produce(
            args.topic,
            key=(args.key.encode("utf-8") if args.key is not None else None),
            value=args.message.encode("utf-8"),
            on_delivery=on_delivery,
        )
    except BufferError as e:
        print(f"ERR: local queue is full: {e}")
        p.poll(1.0)
    remaining = p.flush(args.flush_timeout_s)
    if remaining > 0:
        print(f"WARN: {remaining} message(s) were not delivered before flush timeout")

if __name__ == "__main__":
    main()