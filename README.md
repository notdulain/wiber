# Wiber - Distributed Messaging System (Demo)

This repo contains a minimal working demo of a distributed messaging system prototype to get you started for Scenario 3.

The demo uses Apache Kafka and provides:
- A Kafka producer client to send messages
- A Kafka consumer client to receive messages and optionally fetch recent history
- Fault-tolerant messaging with replication and partitioning
- Persistent message logs with Kafka's built-in durability

## Project structure

- `src/producer/kafka-producer.py` — Kafka producer CLI
- `src/consumer/kafka-consumer.py` — Kafka consumer CLI
- `src/utils/helpers.py` — utility functions
- `docker/docker-compose.kafka.yml` — Kafka cluster setup
- `docs/requirements.txt` — Python dependencies
- `tests/` — add tests here
- `docs/` — place design docs and notes here

## Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Virtual environment (recommended)

## Quick start (local)

### 1. Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r docs/requirements.txt
```

### 2. Start Kafka Cluster

```bash
# Start the Kafka cluster with 3 brokers
docker-compose -f docker/docker-compose.kafka.yml up -d
```

Wait for all services to be healthy (check with `docker-compose ps`).

### 3. Create Fault Tolerant Topic

```bash
# Create topic with 3 partitions and replication factor of 3
docker exec -it kafka-1 kafka-topics.sh --bootstrap-server kafka-1:29092 \
  --create --topic chat --partitions 3 --replication-factor 3

# Require quorum for writes (min.insync.replicas=2)
docker exec -it kafka-1 kafka-configs.sh --bootstrap-server kafka-1:29092 \
  --alter --topic chat --add-config min.insync.replicas=2
```

### 4. Start Consumer and Producer

Open two terminals in the repo root and run:

1) Start a consumer (topic: chat), with the last 5 messages on startup:

```bash
python3 src/consumer/kafka-consumer.py chat --history 5 --bootstrap localhost:9092
```

2) Publish a message:

```bash
python3 src/producer/kafka-producer.py chat 'Hello after fix' --bootstrap localhost:9092
```

You should see the consumer print the message. Messages are persisted by Kafka across broker restarts.

## Kafka Commands Reference
Producer commands:
- `python3 src/producer/kafka-producer.py <topic> <message> --bootstrap <broker>`

Consumer commands:
- `python3 src/consumer/kafka-consumer.py <topic> --bootstrap <broker>`
- `python3 src/consumer/kafka-consumer.py <topic> --history <n> --bootstrap <broker>`
- `python3 src/consumer/kafka-consumer.py <topic> --group <group> --bootstrap <broker>`

## Fault Tolerance Features
This demo implements fault tolerance through:
- **Replication Factor 3**: Each message replicated across 3 brokers
- **Minimum In-Sync Replicas**: Requires at least 2 replicas to acknowledge writes
- **Partitioning**: Topic split into 3 partitions for parallel processing
- **Consumer Groups**: Multiple consumers can process messages in parallel

## Testing Fault Tolerance
1. **Kill a broker**: `docker stop kafka-2`
2. **Continue producing/consuming**: System should continue working
3. **Restart broker**: `docker start kafka-2`
4. **Verify recovery**: Check that the broker rejoins the cluster

## How to extend this into the full assignment (Scenario 3)
Below are the core components you'll build out, mapped to the scenario's focus areas:

1) Fault Tolerance
- Redundancy: Kafka's built-in replication across multiple broker nodes.
- Failure detection: Kafka's built-in heartbeats and timeouts.
- Automatic failover: Kafka's automatic leader election and client discovery.
- Recovery: Kafka's built-in log replication and catch-up mechanisms.
- Evaluation: measure latency/throughput with/without replication.

2) Data Replication and Consistency
- Strategy: Kafka's quorum acks (write succeeds when min.insync.replicas acknowledge).
- Consistency model: Kafka's strong consistency within partitions.
- Deduplication: Kafka's message IDs and consumer offsets.
- Retrieval: Kafka's offset-based and timestamp-based message retrieval.

3) Time Synchronization
- Synchronize clocks across nodes (NTP) and record both logical and physical timestamps.
- Ordering: Kafka's partition-level ordering with custom global ordering if needed.
- Reordering: buffer and reorder on delivery when needed, with bounded waiting.
- Correction: annotate messages with drift/skew metadata for debugging.

4) Consensus and Agreement
- Leader election: Kafka's built-in leader election for partitions.
- Log replication: Kafka's built-in log replication with ISR (In-Sync Replicas).
- Performance: Kafka's batch processing and pipelining optimizations.
- Testing: simulate partitions, crashes, and recoveries; verify safety and liveness properties.

5) Integration & Ops
- Service discovery: Kafka's built-in broker discovery.
- Durability: Kafka's configurable fsync policies and log segments.
- Security: Kafka's SASL/SSL authentication and authorization.
- Observability: Kafka's JMX metrics, structured logs, and monitoring tools.

## Next steps
- Implement custom message ordering across partitions.
- Add custom message IDs and deduplication logic.
- Implement custom consensus algorithms on top of Kafka.
- Add tests under `tests/` (unit + integration) and basic benchmarks.

## Cleanup
```bash
# Stop and remove containers
docker-compose -f docker/docker-compose.kafka.yml down

# Remove volumes (optional - removes all data)
docker-compose -f docker/docker-compose.kafka.yml down -v
```

## Notes
- Kafka persists messages across broker restarts automatically.
- Consumer offsets are maintained by Kafka automatically.
- The system can tolerate 1 broker failure (with RF=3, min.insync.replicas=2).
- To change Kafka settings, modify `docker/docker-compose.kafka.yml`.
