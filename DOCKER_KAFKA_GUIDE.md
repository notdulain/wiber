# 🐳 Docker & Kafka Implementation Guide for Wiber

## 📚 Table of Contents
1. [What is Docker?](#what-is-docker)
2. [What is Kafka?](#what-is-kafka)
3. [Understanding Your Setup](#understanding-your-setup)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Testing & Verification](#testing--verification)

---

## 🐳 What is Docker?

### Simple Explanation
**Docker** is like a shipping container for your software. Just like how shipping containers can hold any cargo and work on any ship, Docker containers can hold your application and run on any computer.

### Key Concepts:

1. **Container**: A lightweight, standalone package that includes everything needed to run your application (code, runtime, libraries, settings)

2. **Image**: A blueprint/template for containers (like a recipe)

3. **Docker Compose**: A tool for defining and running multi-container applications (like Kafka + MongoDB + your app)

### Why Docker for Wiber?
- ✅ **Consistency**: Works the same on everyone's computer
- ✅ **Isolation**: Kafka, MongoDB, and your app don't interfere with each other
- ✅ **Easy Setup**: One command starts everything
- ✅ **Production-Ready**: Same setup works in development and production

---

## 📨 What is Kafka?

### Simple Explanation
**Apache Kafka** is like a super-fast postal service for messages between different parts of your application.

### Key Concepts:

#### 1. **Topic** (like a mailbox)
```
Topic: "chat"
- User sends message → stored in "chat" topic
- Other users subscribe to "chat" topic → receive messages
```

#### 2. **Producer** (sender)
```python
# Your API sends messages to Kafka
producer.send('chat', message_data)
```

#### 3. **Consumer** (receiver)
```python
# Your consumer reads messages from Kafka and saves to MongoDB
consumer.subscribe(['chat'])
for message in consumer:
    save_to_mongodb(message)
```

#### 4. **Partition** (for parallelism)
```
Topic "chat" split into 3 partitions:
Partition 0: [msg1, msg4, msg7]
Partition 1: [msg2, msg5, msg8]
Partition 2: [msg3, msg6, msg9]
```
This allows multiple consumers to read messages in parallel!

#### 5. **Offset** (position tracking)
```
Partition 0: [msg1, msg2, msg3, msg4, msg5]
                ↑               ↑
           offset=0        offset=3
```
Kafka tracks which message each consumer last read.

### Why Kafka for Wiber?

| Feature | Benefit |
|---------|---------|
| **Durability** | Messages saved to disk, not lost if app crashes |
| **Scalability** | Handles millions of messages per second |
| **Ordering** | Messages in same partition stay in order |
| **Replication** | Multiple copies prevent data loss |
| **Fault Tolerance** | System keeps working if parts fail |

---

## 🏗️ Understanding Your Setup

### Your Current docker-compose.yml

```yaml
services:
  kafka:           # Message queue service
  akhq:            # Kafka web UI (view topics/messages)
  mongodb:         # Database for storing messages
```

### What's Missing?
1. **API Service** - Your REST API to send/receive messages
2. **Consumer Service** - Reads from Kafka and saves to MongoDB
3. **Proper Configuration** - Environment variables for connection

---

## 🚀 Step-by-Step Implementation

### Architecture Overview

```
User Request
    ↓
[REST API] -----(Kafka Producer)----→ [Kafka Topic: "wiber.messages"]
                                            ↓
                                    [Consumer Service]
                                            ↓
                                      [MongoDB]
                                            ↓
[REST API] ←--(read from database)-- [MongoDB]
```

### File Structure
```
wiber/
├── docker/
│   ├── docker-compose.yml          # All services
│   ├── Dockerfile.api              # API container
│   └── Dockerfile.consumer         # Consumer container
├── src/
│   ├── api/
│   │   └── rest_api.py            # FastAPI endpoints
│   ├── producer/
│   │   └── producer.py            # Kafka producer
│   ├── consumer/
│   │   └── consumer.py            # Kafka consumer
│   ├── database/
│   │   └── mongodb_handler.py     # MongoDB operations
│   └── config/
│       └── settings.py            # Configuration
└── requirements.txt
```

---

## 📋 Implementation Steps

### Step 1: Install Dependencies

Create/update `requirements.txt`:
```txt
fastapi==0.104.1
uvicorn==0.24.0
kafka-python==2.0.2
pymongo==4.6.0
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0
```

### Step 2: Configuration

Update `src/config/settings.py`:
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "wiber.messages")
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "wiber-consumers")
    
    # MongoDB Settings
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "wiber")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "messages")
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Step 3: Kafka Producer

Create `src/producer/producer.py`:
```python
from kafka import KafkaProducer
import json
import uuid
import time
from src.config.settings import settings

class MessageProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Fault Tolerance Settings (Member 1's responsibility)
            acks='all',  # Wait for all replicas
            retries=10,  # Retry on failure
            enable_idempotence=True  # Exactly-once semantics
        )
    
    def send_message(self, from_user: str, to_user: str, content: str):
        message = {
            'messageId': str(uuid.uuid4()),
            'fromUser': from_user,
            'toUser': to_user,
            'content': content,
            'timestamp': int(time.time() * 1000)  # Milliseconds
        }
        
        # Use conversation key for ordering (Member 3's responsibility)
        key = f"{from_user}:{to_user}"
        
        future = self.producer.send(
            settings.KAFKA_TOPIC,
            key=key,
            value=message
        )
        
        # Wait for confirmation
        record = future.get(timeout=10)
        return message
    
    def close(self):
        self.producer.flush()
        self.producer.close()
```

### Step 4: Kafka Consumer

Create `src/consumer/consumer.py`:
```python
from kafka import KafkaConsumer
import json
import logging
from src.database.mongodb_handler import MongoDBHandler
from src.config.settings import settings

logger = logging.getLogger(__name__)

class MessageConsumer:
    def __init__(self):
        self.consumer = KafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            # Fault Tolerance Settings (Member 1's responsibility)
            enable_auto_commit=False,  # Manual commit after processing
            auto_offset_reset='earliest'  # Start from beginning if no offset
        )
        self.db = MongoDBHandler()
    
    def start(self):
        logger.info("Consumer started, listening for messages...")
        
        try:
            for message in self.consumer:
                try:
                    # Process message
                    msg_data = message.value
                    logger.info(f"Received message: {msg_data['messageId']}")
                    
                    # Save to MongoDB (Member 2's responsibility - replication)
                    self.db.save_message(msg_data)
                    
                    # Commit offset only after successful save
                    # This ensures at-least-once delivery
                    self.consumer.commit()
                    
                    logger.info(f"Message {msg_data['messageId']} processed successfully")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Could send to Dead Letter Queue here (Member 1's responsibility)
                    
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
        finally:
            self.consumer.close()
```

### Step 5: MongoDB Handler

Create `src/database/mongodb_handler.py`:
```python
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
import logging
from src.config.settings import settings

logger = logging.getLogger(__name__)

class MongoDBHandler:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.collection = self.db[settings.MONGO_COLLECTION]
        
        # Create indexes for performance and deduplication
        # (Member 2's responsibility - replication & consistency)
        self._create_indexes()
    
    def _create_indexes(self):
        # Unique index on messageId to prevent duplicates
        self.collection.create_index([("messageId", ASCENDING)], unique=True)
        
        # Compound index for fast conversation queries
        self.collection.create_index([
            ("fromUser", ASCENDING),
            ("toUser", ASCENDING),
            ("timestamp", ASCENDING)
        ])
    
    def save_message(self, message_data: dict):
        try:
            # Member 2's responsibility: Use write concern for durability
            result = self.collection.insert_one(message_data)
            logger.info(f"Message saved with ID: {result.inserted_id}")
            return True
        except DuplicateKeyError:
            # Message already exists (idempotency)
            logger.warning(f"Duplicate message: {message_data['messageId']}")
            return True  # Still return success
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
    
    def get_messages(self, user1: str, user2: str, limit: int = 50):
        # Member 3's responsibility: Maintain order by timestamp
        query = {
            "$or": [
                {"fromUser": user1, "toUser": user2},
                {"fromUser": user2, "toUser": user1}
            ]
        }
        
        messages = self.collection.find(query).sort("timestamp", ASCENDING).limit(limit)
        return list(messages)
```

### Step 6: REST API

Create `src/api/rest_api.py`:
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from src.producer.producer import MessageProducer
from src.database.mongodb_handler import MongoDBHandler

logger = logging.getLogger(__name__)
app = FastAPI(title="Wiber Messaging API")

# Initialize producer and database
producer = MessageProducer()
db = MongoDBHandler()

class MessageRequest(BaseModel):
    fromUser: str
    toUser: str
    content: str

class MessageResponse(BaseModel):
    messageId: str
    fromUser: str
    toUser: str
    content: str
    timestamp: int

@app.post("/messages", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message via Kafka"""
    try:
        message = producer.send_message(
            from_user=request.fromUser,
            to_user=request.toUser,
            content=request.content
        )
        return message
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/messages/{user1}/{user2}", response_model=List[MessageResponse])
async def get_messages(user1: str, user2: str, limit: int = 50):
    """Get messages between two users"""
    try:
        messages = db.get_messages(user1, user2, limit)
        return messages
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/liveness")
async def liveness():
    """Check if service is alive"""
    return {"status": "alive"}

@app.get("/health/readiness")
async def readiness():
    """Check if service is ready (can reach Kafka & MongoDB)"""
    try:
        # Test Kafka connection
        producer.producer.bootstrap_connected()
        
        # Test MongoDB connection
        db.client.admin.command('ping')
        
        return {"status": "ready", "kafka": "connected", "mongodb": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {str(e)}")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    producer.close()
```

### Step 7: Docker Files

Create `docker/Dockerfile.api`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Run API
CMD ["uvicorn", "src.api.rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker/Dockerfile.consumer`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Run consumer
CMD ["python", "-m", "src.consumer.consumer"]
```

### Step 8: Update docker-compose.yml

Update your `docker/docker-compose.yml` to include API and consumer services.

---

## 🧪 Testing & Verification

### Start Everything
```bash
cd docker
docker compose up -d
```

### Check Services
```bash
docker compose ps
```

### Test API
```bash
# Send a message
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser": "alice", "toUser": "bob", "content": "Hello!"}'

# Get messages
curl http://localhost:8000/messages/alice/bob
```

### View Kafka Topics
1. Open AKHQ: http://localhost:8080
2. Navigate to Topics → `wiber.messages`
3. See your messages!

### View MongoDB
1. Install MongoDB Compass
2. Connect to: `mongodb://localhost:27017`
3. Database: `wiber` → Collection: `messages`

---

## 🎓 Key Takeaways

### Docker
- **Container** = Your app in a box
- **Image** = Blueprint for container
- **Compose** = Orchestrate multiple containers
- **Command**: `docker compose up` = Start everything

### Kafka
- **Topic** = Message category/channel
- **Producer** = Sends messages
- **Consumer** = Reads messages
- **Partition** = Splits topic for parallelism
- **Offset** = Position in message log

### Your System Flow
```
User → API → Kafka → Consumer → MongoDB → API → User
```

---

## 📚 Next Steps

1. ✅ Reorganize files (DONE)
2. ⬜ Implement producer.py
3. ⬜ Implement consumer.py
4. ⬜ Update docker-compose.yml
5. ⬜ Create Dockerfiles
6. ⬜ Test end-to-end
7. ⬜ Add fault tolerance (DLQ, retries)
8. ⬜ Add monitoring & logging

Want me to implement any of these next?

