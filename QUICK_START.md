# 🚀 Wiber Quick Start Guide

## Prerequisites
- Docker Desktop installed and running
- Git Bash / PowerShell / Terminal

## Step 1: Start the System

### Open terminal in the project root directory

```bash
# Navigate to docker directory
cd docker

# Start all services (Kafka, MongoDB, API, Consumer, AKHQ)
docker compose up -d

# Check if services are running
docker compose ps
```

You should see:
- `wiber-kafka` - Running
- `wiber-mongodb` - Running  
- `wiber-api` - Running
- `wiber-consumer` - Running
- `wiber-akhq` - Running

## Step 2: Wait for Services to be Ready

```bash
# Check API health
curl http://localhost:8000/health/readiness

# Or in PowerShell
Invoke-WebRequest http://localhost:8000/health/readiness
```

Wait until you see: `{"status":"ready","kafka":"connected","mongodb":"connected"}`

## Step 3: Test the System

### Send a Message

```bash
# Using curl (Git Bash / Linux / Mac)
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "fromUser": "alice",
    "toUser": "bob",
    "content": "Hello Bob! How are you?"
  }'

# Using PowerShell
$body = @{
    fromUser = "alice"
    toUser = "bob"
    content = "Hello Bob! How are you?"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/messages -Method Post -Body $body -ContentType "application/json"
```

### Retrieve Messages

```bash
# Using curl
curl http://localhost:8000/messages/alice/bob

# Using PowerShell
Invoke-RestMethod http://localhost:8000/messages/alice/bob
```

## Step 4: Monitor the System

### View API Documentation
Open browser: http://localhost:8000/docs

Interactive API documentation with "Try it out" buttons!

### View Kafka Topics & Messages
Open browser: http://localhost:8080

- Navigate to **Topics** → `wiber.messages`
- See your messages in real-time!

### View MongoDB Data
1. Install **MongoDB Compass**: https://www.mongodb.com/try/download/compass
2. Connect to: `mongodb://localhost:27017`
3. Database: `wiber` → Collection: `messages`

### View Logs

```bash
# API logs
docker logs wiber-api -f

# Consumer logs
docker logs wiber-consumer -f

# All logs
docker compose logs -f
```

## Step 5: Test Different Scenarios

### Send Multiple Messages

```bash
# Send from alice to bob
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"alice","toUser":"bob","content":"Message 1"}'

# Send from bob to alice
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"bob","toUser":"alice","content":"Message 2"}'

# Get conversation
curl http://localhost:8000/messages/alice/bob
```

### Test Fault Tolerance (Member 1)

```bash
# Kill the consumer
docker stop wiber-consumer

# Send messages (they'll queue in Kafka)
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"alice","toUser":"bob","content":"Message during downtime"}'

# Restart consumer (messages will be processed)
docker start wiber-consumer

# Check logs
docker logs wiber-consumer -f
```

### Scale Consumers (Member 4 - Consensus)

```bash
# Run 3 consumer instances
docker compose up -d --scale consumer=3

# Check partition assignment in logs
docker logs wiber-consumer -f
```

## Step 6: Stop the System

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clears data)
docker compose down -v
```

## Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker ps

# View errors
docker compose logs

# Rebuild containers
docker compose build --no-cache
docker compose up -d
```

### Can't connect to API
```bash
# Check if API is healthy
docker logs wiber-api

# Check port is not in use
netstat -an | findstr :8000  # Windows
lsof -i :8000                # Mac/Linux
```

### Kafka connection issues
```bash
# Check Kafka is healthy
docker logs wiber-kafka

# Check Kafka topics
docker exec wiber-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```

### MongoDB connection issues
```bash
# Check MongoDB is healthy
docker logs wiber-mongodb

# Test connection
docker exec wiber-mongodb mongosh --eval "db.runCommand({ ping: 1 })"
```

## Common Commands

```bash
# View all containers
docker compose ps

# View logs for a service
docker logs <container-name> -f

# Restart a service
docker compose restart <service-name>

# Rebuild a service
docker compose build <service-name>
docker compose up -d <service-name>

# Execute command in container
docker exec -it <container-name> bash

# Clean everything
docker compose down -v
docker system prune -a
```

## Next Steps

1. ✅ Basic system working
2. ⬜ Implement Dead Letter Queue (Member 1)
3. ⬜ Add write concern testing (Member 2)
4. ⬜ Implement clock sync testing (Member 3)
5. ⬜ Add leader election demo (Member 4)
6. ⬜ Create monitoring dashboard (Member 5)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Welcome message |
| POST | /messages | Send a message |
| GET | /messages/{user1}/{user2} | Get conversation |
| GET | /messages/user/{username} | Get user's messages |
| GET | /messages/count | Count messages |
| GET | /health/liveness | Liveness probe |
| GET | /health/readiness | Readiness probe |
| GET | /docs | API documentation |

## Default Ports

| Service | Port | URL |
|---------|------|-----|
| API | 8000 | http://localhost:8000 |
| AKHQ (Kafka UI) | 8080 | http://localhost:8080 |
| MongoDB | 27017 | mongodb://localhost:27017 |
| Kafka | 9092 | kafka://localhost:9092 |

## Environment Variables

Create `.env` file in project root:

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC=wiber.messages
KAFKA_CONSUMER_GROUP=wiber-consumers

# MongoDB
MONGO_URI=mongodb://mongodb:27017
MONGO_DB=wiber
MONGO_COLLECTION=messages

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

**Need help?** Check the full guide in `DOCKER_KAFKA_GUIDE.md`

