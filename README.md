# Wiber - Dead Letter Queue (learning_5)

This repo contains a distributed messaging system prototype implementing core distributed systems concepts for Scenario 3.

## Current Features

The system provides:
- **TCP broker** (server) supporting PUB/SUB, ACK, HEARTBEAT, and HISTORY commands
- **Publisher client** to send messages with unique IDs and offsets
- **Subscriber client** to receive messages, send acknowledgments, and periodic heartbeats
- **Consumer groups** for horizontal scaling and load balancing
- **Message acknowledgments** for reliable delivery and processing confirmation
- **Heartbeat mechanism** for liveness detection and failure monitoring
- **Dead consumer detection** with automatic message redistribution
- **Dead Letter Queue (DLQ)** for handling persistently failing messages
- **Exponential backoff retry** with configurable retry limits
- **ACK timeout and retry** mechanisms for fault tolerance
- **Persistent per-topic logs** under `data/` (JSONL format with message IDs and offsets)
- **Message deduplication** through unique message IDs
- **Consumer position tracking** through sequential offsets
- **Asynchronous I/O** for handling multiple concurrent clients
- **Round-robin message distribution** across consumer group members
- **Backpressure control** to prevent consumer overload
- **Automatic failure recovery** and message redistribution

## Project structure

- `src/api/broker.py` — asyncio TCP broker
- `src/producer/publisher.py` — simple publisher CLI
- `src/consumer/subscriber.py` — simple subscriber CLI
- `src/database/storage.py` — append/read per-topic logs
- `src/config/settings.py` — host/port and data directory
- `docs/` — place design docs and notes here
- `tests/` — add tests here
- `docker/` — add containerization assets here

## Prerequisites
- Python 3.8+

## Quick start (local)
Open three terminals in the repo root and run:

1) Start the broker:

```bash
python -m src.api.broker
```

2) Start a subscriber (topic: chat), with the last 5 messages on startup:

```bash
# Regular subscriber (broadcast mode)
python -m src.consumer.subscriber chat --history 5

# Consumer group member (load balanced mode)
python -m src.consumer.subscriber chat --group processors --history 5
```

3) Publish a message:

```bash
python -m src.producer.publisher chat "Hello, distributed world!"
```

You should see the subscriber print lines like:
- `HISTORY chat <id> <offset> <ts> <message>` for history entries
- `MSG chat <id> <offset> <ts> Hello, distributed world!` for new messages

**Consumer Groups:** Multiple subscribers in the same group share work - each message goes to only one consumer in the group (load balanced).

Messages are persisted to `./data/chat.log` as JSON lines with unique IDs and offsets. You can restart the broker/subscriber and still fetch history.

## Minimal wire protocol
Client -> Broker:
- `SUB <topic> [group_id]` - Subscribe to topic (optionally in consumer group)
- `PUB <topic> <message...>` - Publish message
- `ACK <message_id>` - Acknowledge message processing
- `HEARTBEAT` - Periodic "I'm alive" signal
- `HISTORY <topic> <n>` - Get last n messages
- `PING` | `QUIT` - Health check / disconnect

Broker -> Client:
- `OK <desc>` | `ERR <desc>`
- `MSG <topic> <id> <offset> <ts> <message>`
- `HISTORY <topic> <id> <offset> <ts> <message>`

## How to extend this into the full assignment (Scenario 3)
Below are the core components you’ll build out, mapped to the scenario’s focus areas:

1) Fault Tolerance
- Redundancy: replicate each topic’s log to multiple broker nodes (e.g., primary + followers).
- Failure detection: heartbeats and timeouts between brokers and from clients to brokers.
- Automatic failover: clients discover a new leader on failure (via a small registry or consensus state).
- Recovery: followers catch up from the leader’s log (or via snapshotting + incremental replication).
- Evaluation: measure latency/throughput with/without replication.

2) Data Replication and Consistency
- Strategy: start with primary–replica and quorum acks (e.g., write succeeds when W out of N replicas ack).
- Consistency model: pick strong (leader-based) or eventual (gossip-based). Justify trade-offs.
- Deduplication: message IDs with idempotent writes and consumer offsets to avoid double delivery.
- Retrieval: index logs by offset/timestamp; allow range reads and pagination for efficient fetch.

3) Time Synchronization
- Synchronize clocks across nodes (NTP) and record both logical and physical timestamps.
- Ordering: use Lamport or vector clocks to reason about causal ordering across brokers.
- Reordering: buffer and reorder on delivery when needed, with bounded waiting.
- Correction: annotate messages with drift/skew metadata for debugging.

4) Consensus and Agreement
- Leader election and log replication with Raft (or Paxos if you prefer).
- Use Raft for: choosing the leader, committing message appends, and agreeing on configuration changes.
- Performance: batch appends, pipeline replication, and tune timeouts.
- Testing: simulate partitions, crashes, and recoveries; verify safety and liveness properties.

5) Integration & Ops
- Service discovery: static config at first, then a simple registry (file/DNS) or a lightweight coordinator.
- Durability: fsync policy, segment the commit log, compaction and snapshots.
- Security: mTLS between components, authN/Z for producers/consumers.
- Observability: structured logs, metrics (latency, throughput, lag), tracing.

## Implemented Features

### Message IDs and Offsets ✅
- **Unique Message IDs**: Each message gets a unique identifier (`msg_{timestamp}_{random_hex}`)
- **Sequential Offsets**: Messages are numbered sequentially within each topic (1, 2, 3, ...)
- **Enhanced Protocol**: Messages now include ID and offset in the wire protocol
- **Deduplication**: Message IDs enable detection and prevention of duplicate processing
- **Position Tracking**: Offsets allow consumers to track their position and resume from specific points

### Consumer Groups ✅
- **Horizontal Scaling**: Multiple consumers share work within the same group
- **Load Balancing**: Messages are distributed evenly using round-robin algorithm
- **Fault Tolerance**: If one consumer fails, others continue processing
- **Dual Mode**: Regular subscribers (broadcast) and consumer groups (load balanced)
- **Group Coordination**: Broker manages group membership and message distribution

### Message Acknowledgments ✅
- **Reliable Delivery**: Consumer confirms message processing with ACK command
- **Pending Message Tracking**: Broker tracks unacknowledged messages per consumer
- **ACK Timeout**: Automatic cleanup of messages that aren't acknowledged within 30 seconds
- **Backpressure Control**: Limits pending messages per consumer (max 5) to prevent overload
- **Error Handling**: Graceful handling of ACK timeouts and consumer disconnections
- **Processing Confirmation**: Only ACKed messages are considered successfully processed

### Heartbeats and Failure Detection ✅
- **Liveness Detection**: Consumers send periodic HEARTBEAT signals (every 10 seconds)
- **Dead Consumer Detection**: Broker detects consumers that haven't sent heartbeats in 30 seconds
- **Automatic Message Redistribution**: Pending messages from dead consumers are redistributed to alive consumers
- **Connection Health Monitoring**: Real-time tracking of consumer connection status
- **Graceful Failure Handling**: System continues operating when consumers fail
- **Background Monitoring**: Separate monitoring tasks for heartbeats and ACK timeouts

### Dead Letter Queue (DLQ) ✅
- **Retry Counter**: Tracks number of retry attempts per message
- **Exponential Backoff**: Increasing delays between retries (1s, 2s, 4s)
- **Retry Limits**: Maximum 3 attempts before sending to DLQ
- **DLQ Topics**: Failed messages sent to `{topic}.dlq` topics
- **Failure Metadata**: DLQ messages include retry count, failure reason, and timestamps
- **Automatic Cleanup**: Retry tracking cleaned up after DLQ routing

### Message Format
```json
{
  "id": "msg_1758865780040_e10628bb",
  "offset": 3,
  "ts": 1758865780.0369835,
  "msg": "Hello, distributed world!"
}
```

## Next Steps
- **DLQ Monitoring**: Dashboard for viewing and managing DLQ messages
- **Message Replay**: Replay messages from DLQ after fixing issues
- **Consumer Health Metrics**: Track consumer performance and load
- **Multi-broker Architecture**: Split broker into multiple nodes with leader-follower replication
- **Raft Consensus**: Implement leader election and log replication
- **Tests**: Add unit and integration tests under `tests/`

## Distributed Systems Concepts Demonstrated

This system implements several core distributed systems concepts:

### 1. Publisher-Subscriber Pattern
- **Publishers** send messages to specific topics
- **Subscribers** listen to topics they're interested in
- **Broker** acts as intermediary, routing messages from publishers to subscribers

### 2. Message Persistence
- Messages are stored in JSONL files and survive broker restarts
- Enables message durability and replay capabilities
- Foundation for reliable message delivery

### 3. Asynchronous I/O
- Uses Python's `asyncio` for handling multiple clients simultaneously
- Non-blocking operations for better performance and resource utilization
- Enables concurrent message processing

### 4. Message Identification
- **Message IDs**: Unique identifiers for each message
- **Offsets**: Sequential position numbers within topics
- Enables message deduplication and reliable delivery
- Foundation for consumer position tracking

### 5. Topic-based Routing
- Messages are organized by topics (like channels)
- Enables selective message delivery
- Supports multiple message streams

### 6. Consumer Groups and Load Balancing
- **Consumer Groups**: Multiple consumers share work within the same group
- **Round-robin Distribution**: Messages are distributed evenly across group members
- **Horizontal Scaling**: Add more consumers to increase throughput
- **Fault Tolerance**: If one consumer fails, others continue processing
- **Dual Mode**: Regular subscribers (broadcast) and consumer groups (load balanced)

### 7. Client Connection Management
- Tracks active client connections
- Handles client disconnections gracefully
- Manages subscription state and group membership

### 8. Simple Wire Protocol
- Text-based commands over TCP
- Easy to understand and debug
- Enables interoperability between different clients
- Supports both regular subscriptions and consumer groups

### 9. Error Handling
- Handles connection errors gracefully
- Provides meaningful error messages
- Implements basic fault tolerance

### 10. Message Acknowledgments and Reliable Delivery
- **ACK Protocol**: Consumers send ACK commands after processing messages
- **Pending Message Tracking**: Broker maintains pending messages per consumer
- **Timeout Management**: Automatic cleanup of unacknowledged messages (30s timeout)
- **Backpressure Control**: Limits pending messages per consumer (max 5)
- **Reliable Processing**: Only ACKed messages are considered successfully processed
- **Flow Control**: Prevents consumer overload and manages processing rate

### 11. Heartbeats and Failure Detection
- **Liveness Monitoring**: Periodic heartbeat signals to detect alive consumers
- **Failure Detection**: Time-based detection of dead consumers (30s timeout)
- **Automatic Recovery**: Redistribution of pending messages from dead consumers
- **Connection Health**: Real-time monitoring of consumer connection status
- **Background Monitoring**: Asynchronous monitoring tasks for system health
- **Graceful Degradation**: System continues operating despite consumer failures

### 12. Dead Letter Queue and Retry Logic
- **Failure Classification**: Distinguishes between temporary and permanent failures
- **Exponential Backoff**: Increasing delays between retry attempts (1s, 2s, 4s)
- **Retry Limits**: Prevents infinite retry loops with maximum attempt limits
- **DLQ Routing**: Failed messages sent to dedicated dead letter topics
- **Failure Analysis**: Metadata tracking for understanding failure patterns
- **Resource Management**: Prevents system overload from persistent failures

## Consumer Groups Usage Examples

### Basic Consumer Group Setup
```bash
# Terminal 1: Start broker
python -m src.api.broker

# Terminal 2: Consumer 1 in group "processors"
python -m src.consumer.subscriber chat --group processors

# Terminal 3: Consumer 2 in group "processors"
python -m src.consumer.subscriber chat --group processors

# Terminal 4: Consumer 3 in group "processors"
python -m src.consumer.subscriber chat --group processors

# Terminal 5: Publish messages
python -m src.producer.publisher chat "Message 1"
python -m src.producer.publisher chat "Message 2"
python -m src.producer.publisher chat "Message 3"
python -m src.producer.publisher chat "Message 4"
```

### Expected Message Distribution
- **Message 1** → Consumer 1
- **Message 2** → Consumer 2
- **Message 3** → Consumer 3
- **Message 4** → Consumer 1 (round-robin)

### Multiple Consumer Groups
```bash
# Group 1: "processors"
python -m src.consumer.subscriber chat --group processors
python -m src.consumer.subscriber chat --group processors

# Group 2: "analyzers"
python -m src.consumer.subscriber chat --group analyzers
python -m src.consumer.subscriber chat --group analyzers

# Regular subscriber (broadcast mode)
python -m src.consumer.subscriber chat
```

### Benefits of Consumer Groups
- **Horizontal Scaling**: Add more consumers to handle more messages
- **Load Balancing**: Work is distributed evenly across consumers
- **Fault Tolerance**: If one consumer fails, others continue
- **Parallel Processing**: Multiple consumers work simultaneously

### Message Acknowledgment Flow
```bash
# Consumer receives message:
MSG chat msg_1758865780040_e10628bb 3 1758865780.0369835 Hello, distributed world!

# Consumer processes message (simulated 0.1s delay)
Processing message msg_1758865780040_e10628bb...

# Consumer sends ACK:
ACK msg_1758865780040_e10628bb

# Broker confirms:
OK ack_received
```

### ACK Features
- **Automatic ACKs**: Consumer groups automatically send ACKs after processing
- **Timeout Protection**: Messages timeout after 30 seconds if not ACKed
- **Backpressure**: Consumers limited to 5 pending messages to prevent overload
- **Error Recovery**: Timed out messages are removed and logged
- **Processing Confirmation**: Only ACKed messages are considered successfully processed

### Heartbeat Flow
```bash
# Consumer sends heartbeat every 10 seconds:
HEARTBEAT

# Broker responds:
OK heartbeat_received

# Broker monitors heartbeats:
Heartbeat received from consumer

# If no heartbeat for 30+ seconds:
Consumer detected as dead - redistributing pending messages
Redistributing 2 pending messages from dead consumer
Redistributed message msg_123 to alive consumer
```

### Failure Detection Features
- **Automatic Heartbeats**: Consumer groups send heartbeats every 10 seconds
- **Dead Consumer Detection**: Consumers without heartbeats for 30+ seconds are marked dead
- **Message Redistribution**: Pending messages from dead consumers are automatically redistributed
- **Graceful Recovery**: System continues operating when consumers fail
- **Background Monitoring**: Separate monitoring tasks track consumer health

### Dead Letter Queue Flow
```bash
# Message fails processing (ACK timeout):
ACK timeout for message msg_123

# Retry with exponential backoff:
Retrying message msg_123 (attempt 1/3) after 1s delay
Retrying message msg_123 (attempt 2/3) after 2s delay
Retrying message msg_123 (attempt 3/3) after 4s delay

# After max retries, send to DLQ:
Message msg_123 exceeded max retries, sending to DLQ
Message msg_123 sent to DLQ topic 'chat.dlq'
```

### DLQ Features
- **Retry Tracking**: Each message tracked with retry count
- **Exponential Backoff**: 1s, 2s, 4s delays between retries
- **DLQ Topics**: Failed messages stored in `{topic}.dlq` files
- **Failure Metadata**: Includes retry count, failure reason, timestamps
- **Automatic Cleanup**: Retry tracking removed after DLQ routing

## Notes
- `data/` is git-ignored; safe to delete if you want a fresh state.
- To change host/port or data directory, set env vars: `WIBER_HOST`, `WIBER_PORT`, `WIBER_DATA_DIR`.
