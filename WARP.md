# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project overview
- Language: Python 3.8+
- Messaging: Apache Kafka (local 3-broker KRaft cluster via Docker Compose)
- CLI apps: src/producer/kafka-producer.py and src/consumer/kafka-consumer.py (confluent_kafka)
- Lint/format/test tooling: flake8, black, pytest

Important note about README
- README describes an earlier TCP-broker prototype (src/api/broker.py, etc.) that is not present in this tree. The current implementation uses Kafka with a producer/consumer. Prefer the commands in this WARP.md for day-to-day work.

Setup
- Create a virtual environment and install deps:
```bash path=null start=null
python3 -m venv .venv
source .venv/bin/activate
pip install -r docs/requirements.txt
# Required by current code (imported by src/*):
pip install confluent-kafka
```
- Optionally set the Kafka bootstrap server (default is localhost:9092 if unset):
```bash path=null start=null
export KAFKA_BOOTSTRAP=localhost:9092
```

Run Kafka locally
- Start the 3-broker KRaft cluster and Kafka UI:
```bash path=null start=null
docker compose -f docker/docker-compose.kafka.yml up -d
```
- Access UI: http://localhost:8080
- Stop the cluster:
```bash path=null start=null
docker compose -f docker/docker-compose.kafka.yml down
```

Common commands
- Producer (publish a message):
```bash path=null start=null
python3 src/producer/kafka-producer.py <topic> "<message>" \
  --bootstrap ${KAFKA_BOOTSTRAP:-localhost:9092}
```
- Consumer (tail live messages; optional history fetch and from-beginning):
```bash path=null start=null
python3 src/consumer/kafka-consumer.py <topic> \
  --from-beginning \
  --history 5 \
  --group chat-consumers \
  --bootstrap ${KAFKA_BOOTSTRAP:-localhost:9092}
```
- Lint and format:
```bash path=null start=null
flake8 src tests
black --check .
# to apply formatting
black .
```
- Run tests:
```bash path=null start=null
pytest -q
```
- Run a single test file / test:
```bash path=null start=null
pytest tests/test_producer.py -q
pytest tests/test_producer.py::test_some_case -q
# or by keyword
pytest -k producer -q
```

High-level architecture
- External Kafka cluster (Docker Compose):
  - 3 brokers (kafka-1, kafka-2, kafka-3) using KRaft mode, exposing EXTERNAL ports 9092, 9094, 9096 on localhost.
  - INTERNAL ports (29092/29094/29096) for inter-broker communication and for the Kafka UI to connect.
  - Kafka UI at :8080 configured to the INTERNAL listeners.
- Producer (src/producer/kafka-producer.py):
  - CLI that publishes a single message to a topic using confluent_kafka. Idempotence enabled, acks=all, small linger for batching, and a delivery callback prints success/err with partition/offset.
  - Bootstrap server is provided via --bootstrap flag or KAFKA_BOOTSTRAP env var.
- Consumer (src/consumer/kafka-consumer.py):
  - CLI that can optionally fetch recent history across all partitions by computing watermarks and assigning start offsets, then switches to group subscription for live consumption.
  - Flags: --from-beginning (sets auto.offset.reset), --history N (tail N messages before live), --group (consumer group id), --bootstrap.
  - Prints HISTORY and MSG lines with topic, partition, offset, timestamp, and value.

Conventions and environment
- Topics are created automatically by the cluster (auto-create enabled in docker-compose). Adjust replication/min ISR in docker/docker-compose.kafka.yml as needed.
- Default bootstrap server: localhost:9092, override with KAFKA_BOOTSTRAP.
- The docs/requirements.txt includes tooling (pytest/flake8/black) and app libs; confluent-kafka is additionally required for the current code.
