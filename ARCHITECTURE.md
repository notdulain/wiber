# 🏗️ Wiber Architecture

## System Overview

```
                    ┌─────────────────────────┐
                    │      User/Client        │
                    └───────────┬─────────────┘
                                │
                     HTTP POST /messages
                     HTTP GET /messages
                                │
                                ↓
        ╔═══════════════════════════════════════════╗
        ║         REST API (Port 8000)              ║
        ║  - FastAPI                                ║
        ║  - Message validation                     ║
        ║  - Health checks                          ║
        ╚═══════════════╦═══════════════════════════╝
                        │
            ┌───────────┴────────────┐
            │                        │
     Kafka Producer              MongoDB Query
            │                        │
            ↓                        ↓
    ╔═══════════════╗        ╔═══════════════╗
    ║     Kafka     ║        ║   MongoDB     ║
    ║  (Port 9092)  ║        ║ (Port 27017)  ║
    ║               ║        ║               ║
    ║ Topic:        ║        ║ Database:     ║
    ║ wiber.messages║        ║ wiber         ║
    ║               ║        ║               ║
    ║ Partitions: 3 ║        ║ Collection:   ║
    ║               ║        ║ messages      ║
    ╚═══════╦═══════╝        ╚═══════════════╝
            │                        ↑
            │                        │
       Kafka Consumer                │
            │                        │
            └────────────────────────┘
                   Save Message
```

## Component Details

### 1. REST API (Port 8000)
**Technology**: FastAPI + Uvicorn
**Responsibilities**:
- Accept HTTP requests from users
- Validate message format
- Produce messages to Kafka
- Query messages from MongoDB
- Provide health checks

**Key Endpoints**:
- `POST /messages` - Send a message
- `GET /messages/{user1}/{user2}` - Get conversation
- `GET /health/readiness` - Check if ready

### 2. Kafka (Port 9092)
**Technology**: Apache Kafka (KRaft mode - no Zookeeper)
**Responsibilities**:
- Queue messages reliably
- Distribute messages across partitions
- Maintain message ordering per partition
- Replicate data for fault tolerance

**Configuration**:
- **Topic**: `wiber.messages`
- **Partitions**: 3 (configurable)
- **Replication Factor**: 1 (dev), 3 (production)
- **Retention**: 7 days (default)

### 3. Consumer Service
**Technology**: Python + kafka-python
**Responsibilities**:
- Subscribe to Kafka topics
- Process messages one by one
- Save to MongoDB
- Commit offset after successful save

**Fault Tolerance**:
- Manual commit (at-least-once delivery)
- Graceful shutdown
- Automatic rebalancing

### 4. MongoDB (Port 27017)
**Technology**: MongoDB 6.0
**Responsibilities**:
- Store messages permanently
- Provide fast queries
- Ensure no duplicates (unique index)
- Maintain data consistency

**Indexes**:
- `messageId` (unique)
- `(fromUser, toUser, timestamp)` (compound)
- `timestamp` (for sorting)

### 5. AKHQ (Port 8080)
**Technology**: Kafka Web UI
**Responsibilities**:
- Monitor Kafka topics
- View messages in real-time
- Inspect consumer groups
- Debug issues

---

## Message Flow

### Sending a Message

```
1. User sends POST request
   ↓
2. API validates request
   ↓
3. API generates messageId & timestamp
   ↓
4. Producer sends to Kafka
   ├─ Key: "alice:bob" (for ordering)
   ├─ Value: {messageId, fromUser, toUser, content, timestamp}
   └─ Topic: "wiber.messages"
   ↓
5. Kafka stores in partition (based on key hash)
   ↓
6. API returns response immediately
   (Message processing continues asynchronously)
```

### Receiving a Message

```
1. Consumer polls Kafka
   ↓
2. Kafka returns next message
   ↓
3. Consumer deserializes JSON
   ↓
4. Consumer saves to MongoDB
   ├─ Unique index prevents duplicates
   └─ Write concern ensures durability
   ↓
5. Consumer commits offset
   (Tells Kafka: "I processed this message")
```

### Querying Messages

```
1. User sends GET request
   ↓
2. API queries MongoDB
   ├─ Filter: fromUser/toUser match
   ├─ Sort: timestamp ascending
   └─ Limit: 50 messages
   ↓
3. MongoDB uses index for fast lookup
   ↓
4. API returns results as JSON
```

---

## Data Flow Diagram

```
┌─────────────┐
│   alice     │  POST /messages
└──────┬──────┘  {from: alice, to: bob, content: "Hi"}
       │
       ↓
┌─────────────────────────────────────────────┐
│  API: Create Message                        │
│  - messageId: "123e4567..."                 │
│  - timestamp: 1696176000000                 │
│  - key: "alice:bob"                         │
└──────┬──────────────────────────────────────┘
       │
       ↓  Kafka.send(topic="wiber.messages", key="alice:bob", value={...})
       │
┌─────────────────────────────────────────────┐
│  Kafka: Store in Partition                  │
│                                             │
│  Partition 0: [msg from alice:charlie]      │
│  Partition 1: [msg from alice:bob] ← HERE   │
│  Partition 2: [msg from bob:charlie]        │
└──────┬──────────────────────────────────────┘
       │
       ↓  Consumer.poll()
       │
┌─────────────────────────────────────────────┐
│  Consumer: Process Message                  │
│  1. Deserialize JSON                        │
│  2. Validate fields                         │
│  3. Save to MongoDB                         │
│  4. Commit offset                           │
└──────┬──────────────────────────────────────┘
       │
       ↓  db.messages.insert_one({...})
       │
┌─────────────────────────────────────────────┐
│  MongoDB: Store Document                    │
│                                             │
│  {                                          │
│    messageId: "123e4567...",                │
│    fromUser: "alice",                       │
│    toUser: "bob",                           │
│    content: "Hi",                           │
│    timestamp: 1696176000000                 │
│  }                                          │
└─────────────────────────────────────────────┘
       │
       ↑  GET /messages/alice/bob
       │
┌─────────────────────────────────────────────┐
│  API: Query Messages                        │
│  db.messages.find({                         │
│    $or: [                                   │
│      {fromUser: "alice", toUser: "bob"},    │
│      {fromUser: "bob", toUser: "alice"}     │
│    ]                                        │
│  }).sort({timestamp: 1})                    │
└──────┬──────────────────────────────────────┘
       │
       ↓  Return JSON array
       │
┌─────────────┐
│     bob     │  [{"messageId": "123...", "content": "Hi", ...}]
└─────────────┘
```

---

## Fault Tolerance Mechanisms

### 1. Producer Fault Tolerance
```
Producer Config:
├─ acks='all'           → Wait for all replicas
├─ retries=10           → Retry on failure
└─ enable_idempotence   → No duplicates in Kafka
```

### 2. Consumer Fault Tolerance
```
Consumer Config:
├─ enable_auto_commit=False  → Manual commit
├─ Save to DB                → At-least-once
└─ Commit offset             → Only after success
```

### 3. Database Fault Tolerance
```
MongoDB Config:
├─ WriteConcern(w='majority')  → Majority replicas confirm
├─ j=True                      → Write to journal (disk)
└─ Unique index on messageId   → No duplicates
```

### 4. System Fault Tolerance
```
Docker Config:
├─ restart: unless-stopped     → Auto-restart on crash
├─ healthcheck                 → Monitor health
└─ depends_on                  → Start in correct order
```

---

## Scaling Strategy

### Horizontal Scaling (Add More Instances)

```
# Scale consumers
docker compose up -d --scale consumer=3

Result:
┌─────────────────────────────────────┐
│  Kafka Topic: wiber.messages (3 partitions)
├─────────────────────────────────────┤
│  Partition 0 → Consumer 1           │
│  Partition 1 → Consumer 2           │
│  Partition 2 → Consumer 3           │
└─────────────────────────────────────┘

Each consumer processes its own partition independently!
```

### Vertical Scaling (More Resources)

```yaml
# In docker-compose.yml
consumer:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
```

---

## Monitoring Points

### 1. API Metrics
- Request rate (requests/sec)
- Response time (latency)
- Error rate (%)
- Active connections

### 2. Kafka Metrics
- Messages produced/sec
- Messages consumed/sec
- Consumer lag (messages behind)
- Partition distribution

### 3. MongoDB Metrics
- Write throughput (writes/sec)
- Read throughput (reads/sec)
- Index hit ratio (%)
- Storage size

### 4. System Metrics
- CPU usage (%)
- Memory usage (%)
- Disk I/O (MB/sec)
- Network traffic (MB/sec)

---

## Security Considerations (Future Work)

### Authentication & Authorization
- Add JWT tokens for API authentication
- Implement user permissions
- Encrypt messages in transit (TLS)

### Network Security
- Use Docker networks to isolate services
- Firewall rules for production
- VPN for remote access

### Data Security
- Encrypt messages at rest in MongoDB
- Rotate credentials regularly
- Audit logs for compliance

---

## Deployment Environments

### Development (Current Setup)
```
- Single machine
- All services in Docker
- No replication (Kafka RF=1, MongoDB single node)
- Local ports exposed
```

### Production (Recommended)
```
- Kubernetes cluster
- Kafka with 3+ brokers (RF=3)
- MongoDB replica set (3+ nodes)
- Load balancer for API
- Prometheus + Grafana monitoring
- Separate networks for security
```

---

This architecture provides:
- ✅ **Fault Tolerance**: Automatic retries, replication, health checks
- ✅ **Consistency**: Unique indexes, ordered reads, write concerns
- ✅ **Scalability**: Horizontal scaling via partitions and consumer groups
- ✅ **Performance**: Async processing, indexed queries, efficient serialization
- ✅ **Observability**: Health endpoints, logs, monitoring UI


