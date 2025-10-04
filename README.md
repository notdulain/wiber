# Wiber - Fault Tolerant Kafka Messaging System

A distributed messaging system demonstrating fault tolerance using Apache Kafka with replication and partitioning.

## Project Structure

- `src/producer/kafka-producer.py` — Kafka producer client
- `src/consumer/kafka-consumer.py` — Kafka consumer client  
- `src/utils/helpers.py` — Utility functions
- `docker/docker-compose.kafka.yml` — Kafka cluster setup
- `docs/requirements.txt` — Python dependencies
- `tests/` — Test files

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Virtual environment (recommended)

## Setup Instructions

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r docs/requirements.txt
```

### 2. Start Kafka Cluster

```bash
# Start the Kafka cluster with 3 brokers
docker-compose -f docker/docker-compose.kafka.yml up -d
```

Wait for all services to be healthy (check with `docker-compose ps`).

### 3. Create Fault Tolerant Topic

Create a replicated, partitioned topic with fault tolerance:

```bash
# Create topic with 3 partitions and replication factor of 3
docker exec -it kafka-1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka-1:29092 \
  --create --topic chat --partitions 3 --replication-factor 3
```

Configure minimum in-sync replicas for fault tolerance:

```bash
# Require quorum for writes (min.insync.replicas=2)
docker exec -it kafka-1 /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka-1:29092 \
  --alter --topic chat --add-config min.insync.replicas=2
```

### 4. Start Multiple Consumers

Open multiple terminal windows and start consumers:

```bash
# Consumer 1 (same consumer group - messages distributed among consumers)
python3 src/consumer/kafka-consumer.py chat --group chat-consumers --bootstrap localhost:9092

# Consumer 2 (same group - load balancing)
python3 src/consumer/kafka-consumer.py chat --group chat-consumers --bootstrap localhost:9092

# Consumer 3 (different group - receives all messages)
python3 src/consumer/kafka-consumer.py chat --group chat-consumers-2 --bootstrap localhost:9092
```

**Note**: Consumers in the same group will share messages (load balancing). Consumers in different groups will receive all messages.

### 5. Start the Producer

```bash
# Send messages to the topic
python3 src/producer/kafka-producer.py chat 'Hello World!' --bootstrap localhost:9092
python3 src/producer/kafka-producer.py chat 'Fault tolerant messaging' --bootstrap localhost:9092
```

## Fault Tolerance Features

- **Replication Factor 3**: Each message is replicated across 3 brokers
- **Minimum In-Sync Replicas**: Requires at least 2 replicas to acknowledge writes
- **Partitioning**: Topic split into 3 partitions for parallel processing
- **Consumer Groups**: Multiple consumers can process messages in parallel

## Testing Fault Tolerance

1. **Kill a broker**: `docker stop kafka-2`
2. **Continue producing/consuming**: System should continue working
3. **Restart broker**: `docker start kafka-2`
4. **Verify recovery**: Check that the broker rejoins the cluster

## Cleanup

```bash
# Stop and remove containers
docker-compose -f docker/docker-compose.kafka.yml down

# Remove volumes (optional - removes all data)
docker-compose -f docker/docker-compose.kafka.yml down -v
```

## Troubleshooting

- **Connection issues**: Ensure Docker containers are running (`docker-compose ps`)
- **Topic not found**: Verify topic creation commands completed successfully
- **Consumer lag**: Check if consumers are running and connected
- **Port conflicts**: Ensure ports 9092-9094 are available

## Notes

- Messages are persisted across broker restarts
- Consumer offsets are maintained automatically
- The system can tolerate 1 broker failure (with RF=3, min.insync.replicas=2)
