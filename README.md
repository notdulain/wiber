# Wiber - Distributed Messaging System

A production-ready distributed messaging system built with **Docker**, **Apache Kafka**, and **MongoDB**, implementing core distributed systems concepts for Scenario 3.

## 🚀 Current Features

### **Core Architecture**
- **Docker containerization** with multi-service orchestration
- **Apache Kafka** (KRaft mode) for reliable message queuing
- **MongoDB** for persistent message storage
- **FastAPI** REST API for message operations
- **AKHQ** web UI for Kafka monitoring

### **Fault Tolerance & Reliability**
- **At-least-once delivery** with manual offset commits
- **Message deduplication** via unique message IDs
- **Automatic retries** with exponential backoff
- **Health checks** for all services
- **Graceful shutdown** and restart policies

### **Scalability & Performance**
- **Horizontal scaling** with multiple consumer instances
- **Partition-based parallelism** in Kafka
- **Indexed MongoDB queries** for fast retrieval
- **Async processing** with Python asyncio

### **Monitoring & Observability**
- **Structured logging** with JSON format
- **Health endpoints** for service monitoring
- **Real-time message tracking** via AKHQ
- **Container health checks** and restart policies

## 📁 Project Structure

```
wiber/
├── docker/                          # Docker configuration
│   ├── docker-compose.yml          # Multi-service orchestration
│   ├── Dockerfile.api              # API container
│   └── Dockerfile.consumer         # Consumer container
│
├── src/                            # Source code
│   ├── api/
│   │   └── rest_api.py            # FastAPI REST endpoints
│   ├── producer/
│   │   └── producer.py            # Kafka producer
│   ├── consumer/
│   │   └── consumer.py            # Kafka consumer
│   ├── database/
│   │   └── mongodb_handler.py     # MongoDB operations
│   └── config/
│       └── settings.py            # Configuration
│
├── scripts/                        # Demo and test scripts
│   ├── test_system.py             # Comprehensive test suite
│   ├── demo_multi_broker.py       # Multi-broker demo
│   ├── smart_client.py            # Smart client
│   ├── start_multi_broker.py      # Multi-broker startup
│   └── test_multi_broker.py       # Multi-broker tests
│
├── guides/                         # Documentation
│   ├── README.md                  # Guide to all guides
│   ├── START_HERE.md              # Entry point
│   ├── SETUP_GUIDE.md             # Environment setup
│   ├── DOCKER_KAFKA_GUIDE.md      # Learning guide
│   ├── QUICK_START.md             # Usage instructions
│   ├── ARCHITECTURE.md            # System design
│   └── IMPLEMENTATION_SUMMARY.md  # Technical details
│
├── tests/                          # Unit tests
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## 🛠️ Prerequisites

- **Docker Desktop** (with Docker Compose)
- **Python 3.11+** (for local development)
- **Git** (for version control)

## 🚀 Quick Start

### **Step 1: Start the System**
```bash
# Clone the repository
git clone <your-repo-url>
cd wiber

# Start all services with Docker
cd docker
docker compose up -d

# Wait 30-60 seconds for services to start
docker compose ps
```

### **Step 2: Test the System**
```bash
# Send a message
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"alice","toUser":"bob","content":"Hello!"}'

# Get messages
curl http://localhost:8000/messages/alice/bob

# Check system health
curl http://localhost:8000/health/readiness
```

### **Step 3: Explore the System**
- **API Documentation**: http://localhost:8000/docs (Interactive Swagger UI)
- **Kafka UI**: http://localhost:8080 (AKHQ - Browse topics and messages)
- **MongoDB**: Connect with MongoDB Compass to `mongodb://localhost:27017`

### **Step 4: Run Tests**
```bash
# Run comprehensive test suite
python scripts/test_system.py
```

## 📊 System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Apache Kafka  │    │   MongoDB       │
│   (Port 8000)   │───▶│   (Port 9092)   │───▶│   (Port 27017)  │
│                 │    │                 │    │                 │
│ • REST API      │    │ • Message Queue │    │ • Message Store │
│ • Health Checks │    │ • Topic: wiber  │    │ • Deduplication │
│ • Validation    │    │ • Partitions    │    │ • Indexing      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AKHQ UI       │    │   Consumer      │    │   Health        │
│   (Port 8080)   │    │   Service       │    │   Monitoring    │
│                 │    │                 │    │                 │
│ • Topic Browser │    │ • Kafka Consumer│    │ • Container     │
│ • Message View  │    │ • MongoDB Writer│    │   Health Checks │
│ • Monitoring    │    │ • Offset Commit │    │ • Restart       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 Message Flow

1. **User** sends HTTP POST to **FastAPI**
2. **FastAPI** validates and sends to **Kafka**
3. **Kafka** stores message in `wiber.messages` topic
4. **Consumer** reads from Kafka and saves to **MongoDB**
5. **User** can GET messages via **FastAPI**
6. **AKHQ** provides real-time monitoring

## 🔧 API Endpoints

### **Message Operations**
```bash
# Send a message
POST /messages
{
  "fromUser": "alice",
  "toUser": "bob", 
  "content": "Hello!"
}

# Get messages between users
GET /messages/{fromUser}/{toUser}?limit=50&offset=0

# Get message count
GET /messages/count
```

### **Health Checks**
```bash
# Liveness check
GET /health/liveness

# Readiness check (includes dependencies)
GET /health/readiness
```

### **Message Format**
```json
{
  "messageId": "msg_1758865780040_e10628bb",
  "fromUser": "alice",
  "toUser": "bob",
  "content": "Hello!",
  "timestamp": 1758865780040,
  "createdAt": "2025-01-27T10:30:00Z"
}
```

## 🎯 Distributed Systems Concepts Implemented

### **1. Fault Tolerance**
- **Kafka Delivery Guarantees**: `acks=all`, retries, idempotent producer
- **Consumer Offset Management**: Manual commits after successful processing
- **Health Monitoring**: Liveness and readiness endpoints
- **Container Restart Policies**: Automatic recovery on failures
- **Message Deduplication**: Unique message IDs prevent duplicates

### **2. Replication & Consistency**
- **Kafka Replication**: Messages replicated across partitions
- **MongoDB Write Concern**: `w="majority", j=True` for durability
- **Consistent Reads**: Indexed queries with proper ordering
- **At-Least-Once Delivery**: Kafka + MongoDB deduplication = effectively exactly-once

### **3. Time & Ordering**
- **Timestamp Generation**: Millisecond precision timestamps
- **Message Ordering**: Per-partition ordering in Kafka
- **Read-Time Sorting**: Stable sort by timestamp + messageId
- **Clock Synchronization**: NTP on host systems

### **4. Consensus & Leadership**
- **Kafka Partition Leadership**: Automatic leader election
- **Consumer Group Coordination**: Partition assignment and rebalancing
- **Service Discovery**: Docker networking for service location
- **Distributed State**: Shared state across containers

### **5. Integration & Monitoring**
- **Docker Compose**: Multi-service orchestration
- **AKHQ Monitoring**: Real-time Kafka monitoring
- **Structured Logging**: JSON logs with correlation IDs
- **Health Checks**: Container and application health monitoring

## 🚀 Key Features

### **Message Processing**
- **Unique Message IDs**: UUID-based identifiers for deduplication
- **Timestamp Ordering**: Millisecond precision for consistent ordering
- **Message Validation**: Input validation and error handling
- **Pagination Support**: Efficient message retrieval with limits and offsets

### **Kafka Integration**
- **Topic Management**: Automatic topic creation and configuration
- **Partition Strategy**: Optimized for parallel processing
- **Offset Management**: Manual commits for reliable processing
- **Consumer Groups**: Horizontal scaling and load balancing

### **MongoDB Storage**
- **Document Storage**: JSON document format for flexibility
- **Indexing**: Optimized queries for fast retrieval
- **Write Concern**: Durability guarantees with majority writes
- **Deduplication**: Unique indexes prevent duplicate messages

### **Docker Orchestration**
- **Multi-Container**: API, Consumer, Kafka, MongoDB, AKHQ
- **Health Checks**: Container and application health monitoring
- **Restart Policies**: Automatic recovery on failures
- **Networking**: Service discovery and communication

### **Monitoring & Observability**
- **AKHQ Dashboard**: Real-time Kafka monitoring
- **Structured Logging**: JSON logs with correlation IDs
- **Health Endpoints**: Liveness and readiness checks
- **Metrics**: Performance and health monitoring

## 🔧 Development Commands

### **Docker Operations**
```bash
# Start all services
cd docker && docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f

# Restart a service
docker compose restart api

# Scale consumers
docker compose up -d --scale consumer=3

# Clean everything
docker compose down -v
```

### **Testing**
```bash
# Run test suite
python scripts/test_system.py

# Test API endpoints
curl http://localhost:8000/health/readiness

# Send test message
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"test","toUser":"user","content":"Test message"}'
```

### **Monitoring**
```bash
# View API logs
docker logs wiber-api -f

# View consumer logs
docker logs wiber-consumer -f

# View Kafka logs
docker logs wiber-kafka -f

# View MongoDB logs
docker logs wiber-mongodb -f
```

## 📚 Documentation

- **📖 [START_HERE.md](guides/START_HERE.md)** - Entry point and overview
- **⚙️ [SETUP_GUIDE.md](guides/SETUP_GUIDE.md)** - Environment setup
- **🎓 [DOCKER_KAFKA_GUIDE.md](guides/DOCKER_KAFKA_GUIDE.md)** - Learning guide
- **🚀 [QUICK_START.md](guides/QUICK_START.md)** - Usage instructions
- **🏗️ [ARCHITECTURE.md](guides/ARCHITECTURE.md)** - System design
- **📋 [IMPLEMENTATION_SUMMARY.md](guides/IMPLEMENTATION_SUMMARY.md)** - Technical details

## 🎯 Next Steps
- **Enhanced Monitoring**: Prometheus metrics and Grafana dashboards
- **Security**: Authentication and authorization
- **Performance**: Load testing and optimization
- **Scaling**: Kubernetes deployment
- **Testing**: Comprehensive test coverage
- **Documentation**: API documentation and user guides

## 🏆 Team Responsibilities

This project implements the 5 core distributed systems concepts:

### **Member 1: Fault Tolerance**
- Kafka delivery guarantees (`acks=all`, retries)
- Consumer offset management and commit strategy
- Health checks and restart policies
- Failure detection and recovery

### **Member 2: Replication & Consistency**
- Kafka replication semantics
- MongoDB write concern and durability
- Message deduplication strategies
- Consistent read operations

### **Member 3: Time & Ordering**
- Timestamp generation and synchronization
- Message ordering guarantees
- Read-time reordering and sorting
- Clock synchronization

### **Member 4: Consensus & Leadership**
- Kafka partition leadership
- Consumer group coordination
- Service discovery and networking
- Distributed state management

### **Member 5: Integration & Monitoring**
- Docker Compose orchestration
- AKHQ monitoring dashboard
- Structured logging and observability
- Health monitoring and alerting

## 🎉 Getting Started

1. **Read the guides**: Start with [START_HERE.md](guides/START_HERE.md)
2. **Set up environment**: Follow [SETUP_GUIDE.md](guides/SETUP_GUIDE.md)
3. **Learn the concepts**: Study [DOCKER_KAFKA_GUIDE.md](guides/DOCKER_KAFKA_GUIDE.md)
4. **Start the system**: Use [QUICK_START.md](guides/QUICK_START.md)
5. **Understand architecture**: Review [ARCHITECTURE.md](guides/ARCHITECTURE.md)

## 📞 Support

- **Documentation**: Check the `guides/` folder
- **Issues**: Review Docker logs for troubleshooting
- **Learning**: Study the code and documentation
- **Community**: Share knowledge and improvements

---

**Built with ❤️ for distributed systems learning**
