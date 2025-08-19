# NVIDIA Orchestrator - Quick Start Guide

## 🚀 Installation

### From Source (Development Mode)
```bash
# Clone the repository
git clone https://github.com/team3/nvidia-orchestrator.git
cd nvidia-orchestrator

# Install in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev,test]"
```

## 📦 Running the Server

### Method 1: Using Entry Points (Recommended)

```bash
# Run the full server (API + Health Monitor)
nvidia-orchestrator-server

# Or using the CLI
nvidia-orchestrator server

# Run only the API
nvidia-orchestrator api

# Run only the health monitor
nvidia-orchestrator monitor
```

### Method 2: Using Python Module

```bash
# Run the full server
python -m nvidia_orchestrator.main

# Run the API server
python -m nvidia_orchestrator.api.app

# Run the health monitor
python -m nvidia_orchestrator.monitoring.health_monitor
```

### Method 3: Using Docker Compose

```bash
# Production mode
docker-compose up -d

# Development mode with hot reload
docker-compose -f docker-compose.dev.yml up

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🔧 CLI Commands

```bash
# Show help
nvidia-orchestrator --help

# Show version
nvidia-orchestrator version

# Run full server (API + Monitor)
nvidia-orchestrator server --host 0.0.0.0 --port 8000

# Run API only
nvidia-orchestrator api --host 0.0.0.0 --port 8000

# Run monitor only
nvidia-orchestrator monitor --interval 60
```

## 📝 Environment Variables

Create a `.env` file or set these environment variables:

```bash
# PostgreSQL Configuration
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/orchestrator

# Monitoring Configuration
HEALTH_INTERVAL_SECONDS=60
HEALTH_RETENTION_DAYS=7

# Logging Configuration
LOG_FILE=/app/logs/combined.log

# Service Discovery (Optional)
REGISTRY_URL=http://registry:8000/registry/endpoints
REGISTRY_API_KEY=your-api-key
```

## 🧪 Testing the Installation

```bash
# Test package imports
python scripts/test_package.py

# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/containers
curl http://localhost:8000/system/resources
```

## 📚 Using as a Library

```python
from nvidia_orchestrator import ContainerManager, PostgresStore, get_logger

# Initialize components
logger = get_logger("my-app")
manager = ContainerManager()
store = PostgresStore()

# Create a container
info = manager.create_container(
    image="nginx:alpine",
    env={"KEY": "value"},
    ports={"80/tcp": 8080},
    resources={"memory_limit": "512m", "cpu_limit": "0.5"}
)

# List containers
containers = manager.list_managed_containers()
for container in containers:
    print(f"Container {container['id']} is {container['state']}")
```

## 🐳 Docker Build Options

```bash
# Build production image
docker build -t nvidia-orchestrator:latest .

# Build development image
docker build --target development -t nvidia-orchestrator:dev .

# Run the image
docker run -p 8000:8000 nvidia-orchestrator:latest

# Run with custom environment
docker run -p 8000:8000 \
  -e POSTGRES_URL=postgresql://user:pass@host:5432/db \
  -v /var/run/docker.sock:/var/run/docker.sock \
  nvidia-orchestrator:latest
```

## 🔍 Verifying the Setup

1. **Check API Health:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check System Resources:**
   ```bash
   curl http://localhost:8000/system/resources
   ```

3. **List Containers:**
   ```bash
   curl http://localhost:8000/containers
   ```

4. **View Logs:**
   ```bash
   tail -f logs/combined.log
   ```

## 📖 Documentation

- [README.md](README.md) - Main documentation
- [docs/README_API.md](docs/README_API.md) - API documentation
- [docs/README_APP.md](docs/README_APP.md) - Application guide
- [docs/README_CONTAINER_SYSTEM.md](docs/README_CONTAINER_SYSTEM.md) - Container system details

## 🆘 Troubleshooting

### Package Not Found
```bash
# Reinstall in development mode
pip uninstall nvidia-orchestrator
pip install -e .
```

### Docker Connection Issues
```bash
# Ensure Docker is running
docker version

# Check Docker socket permissions
ls -la /var/run/docker.sock
```

### PostgreSQL Connection Issues
```bash
# Test PostgreSQL connection
psql postgresql://postgres:postgres@localhost:5432/orchestrator

# Initialize database schema
psql -U postgres -d orchestrator -f scripts/db-init.sql
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
nvidia-orchestrator api --port 8001
``` 