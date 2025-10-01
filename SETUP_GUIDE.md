# 🚀 Complete Setup Guide - venv vs Docker

## Understanding the Two Environments

### 🐳 Docker (For Running the System)
- **What**: Containers with the full application
- **Contains**: Python, Kafka, MongoDB, API, Consumer
- **Use for**: Running the actual Wiber system
- **No venv needed!**

### 🐍 Virtual Environment (For Local Scripts)
- **What**: Isolated Python environment on your machine
- **Contains**: Python packages for scripts
- **Use for**: Running test scripts, demos, development tools
- **Separate from Docker!**

---

## 📋 Initial Setup (Do This Once)

### Step 1: Setup Virtual Environment (for local scripts)

```bash
# Navigate to project root
cd C:\Users\User\Desktop\coding\projects\2025\wiber

# Create virtual environment
python -m venv venv

# Activate it (PowerShell)
.\venv\Scripts\Activate.ps1

# You should see (venv) in your prompt:
# (venv) PS C:\Users\User\Desktop\coding\projects\2025\wiber>

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

### Step 2: Verify Docker is Installed

```bash
# Check Docker is running
docker --version
docker compose --version

# Should output something like:
# Docker version 24.0.x
# Docker Compose version v2.x.x
```

---

## 🎯 Daily Workflow

### Starting Your Work Session:

```bash
# Terminal 1: Start the system with Docker
cd docker
docker compose up -d

# Wait 30-60 seconds for services to start
docker compose ps

# Check health
curl http://localhost:8000/health/readiness
```

```bash
# Terminal 2: Run tests/scripts with venv
# Activate venv (if not already activated)
.\venv\Scripts\Activate.ps1

# Run tests
python scripts/test_system.py

# Or send messages
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"fromUser":"alice","toUser":"bob","content":"Hello!"}'
```

### Ending Your Work Session:

```bash
# Stop Docker containers
cd docker
docker compose down

# Deactivate venv (optional)
deactivate
```

---

## 🔍 What's Running Where?

### When Docker is Running:

```
Docker Containers (isolated from your PC):
┌─────────────────────────────────────┐
│ wiber-api:8000                      │  ← FastAPI + Kafka Producer
│ wiber-consumer                      │  ← Kafka Consumer + MongoDB Writer
│ wiber-kafka:9092                    │  ← Kafka Broker
│ wiber-mongodb:27017                 │  ← MongoDB Database
│ wiber-akhq:8080                     │  ← Kafka UI
└─────────────────────────────────────┘

Your Computer:
┌─────────────────────────────────────┐
│ venv/ (when activated)              │  ← For running test scripts
│ - Python 3.11                       │
│ - requests, pytest, etc.            │
└─────────────────────────────────────┘
```

---

## ✅ Quick Commands Reference

### Virtual Environment Commands:

```bash
# Create venv (once)
python -m venv venv

# Activate (every time you open terminal)
# PowerShell:
.\venv\Scripts\Activate.ps1
# CMD:
.\venv\Scripts\activate.bat
# Git Bash:
source venv/Scripts/activate

# Deactivate (when done)
deactivate

# Install/update packages
pip install -r requirements.txt

# Check what's installed
pip list
```

### Docker Commands:

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View running containers
docker compose ps

# View logs
docker logs wiber-api -f
docker compose logs -f

# Restart a service
docker compose restart api

# Rebuild containers (after code changes)
docker compose build
docker compose up -d

# Clean everything
docker compose down -v
```

---

## 🐛 Troubleshooting

### "venv not activating"

**PowerShell**: You might need to allow scripts:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try again:
```powershell
.\venv\Scripts\Activate.ps1
```

### "Docker containers not starting"

```bash
# Check Docker Desktop is running
docker ps

# Check logs for errors
docker compose logs

# Try rebuilding
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### "Can't connect to API"

```bash
# Check if containers are running
docker compose ps

# Check API logs
docker logs wiber-api -f

# Wait for services to be ready
curl http://localhost:8000/health/readiness
```

---

## 📝 Development Workflow Examples

### Example 1: Making Code Changes

```bash
# 1. Make changes to src/api/rest_api.py
# Edit the file...

# 2. Rebuild and restart
cd docker
docker compose build api
docker compose up -d

# 3. Test changes
curl http://localhost:8000/docs
```

### Example 2: Running Tests

```bash
# 1. Ensure Docker is running
cd docker
docker compose up -d

# 2. Activate venv
.\venv\Scripts\Activate.ps1

# 3. Run tests
python scripts/test_system.py

# Tests will call the Docker API endpoints
```

### Example 3: Debugging with Logs

```bash
# Terminal 1: Watch API logs
docker logs wiber-api -f

# Terminal 2: Watch Consumer logs
docker logs wiber-consumer -f

# Terminal 3: Send test messages (with venv)
.\venv\Scripts\Activate.ps1
python scripts/test_system.py
```

---

## 🎓 Key Takeaways

1. **Docker = Your system runs here**
   - API, Consumer, Kafka, MongoDB
   - No venv needed
   - Start with `docker compose up -d`

2. **venv = Your test scripts run here**
   - test_system.py, demo scripts
   - Local Python environment
   - Activate with `.\venv\Scripts\Activate.ps1`

3. **They work together:**
   - Docker provides the services
   - venv provides tools to test those services

4. **You don't run Docker "inside" venv**
   - They're separate
   - Docker Desktop runs independently
   - venv is just for local Python scripts

---

## ✨ Best Practice

### Terminal Setup (Recommended):

**Terminal 1 (Docker):**
```bash
cd C:\Users\User\Desktop\coding\projects\2025\wiber\docker
docker compose up
# Leave this running (shows logs in real-time)
```

**Terminal 2 (Development):**
```bash
cd C:\Users\User\Desktop\coding\projects\2025\wiber
.\venv\Scripts\Activate.ps1
# Use this for tests, scripts, commands
```

---

## 🎉 You're Ready!

Now you understand:
- ✅ Docker runs your system (containers)
- ✅ venv runs your local scripts
- ✅ They work together but separately
- ✅ No need to activate venv to use Docker

**Next steps:**
1. Activate venv: `.\venv\Scripts\Activate.ps1`
2. Install dependencies: `pip install -r requirements.txt`
3. Start Docker: `cd docker && docker compose up -d`
4. Run tests: `python scripts/test_system.py`

Happy coding! 🚀

