# NVIDIA Orchestrator

A container orchestration system for managing Docker containers with health monitoring and PostgreSQL storage.

## 🏗️ Project Structure

This project follows the **src-layout** pattern for Python packages:

```
nvidia-orchestrator/
├── src/                        # Source code (src-layout)
│   └── nvidia_orchestrator/    # Main package
│       ├── __init__.py        # Package initialization
│       ├── api/               # REST API module
│       │   ├── __init__.py
│       │   └── app.py         # FastAPI application
│       ├── core/              # Core business logic
│       │   ├── __init__.py
│       │   └── container_manager.py
│       ├── storage/           # Data storage layer
│       │   ├── __init__.py
│       │   └── postgres_store.py
│       ├── monitoring/        # Health monitoring
│       │   ├── __init__.py
│       │   └── health_monitor.py
│       ├── utils/             # Utilities
│       │   ├── __init__.py
│       │   └── logger.py
│       └── cli.py             # Command-line interface
├── tests/                      # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── docs/                       # Documentation
│   ├── README_API.md          # API documentation
│   ├── README_APP.md          # Application guide
│   └── README_CONTAINER_SYSTEM.md
├── scripts/                    # Utility scripts
│   ├── start.sh               # Startup script
│   └── db-init.sql            # Database schema
├── pyproject.toml             # Package configuration
├── Dockerfile                 # Container image
├── docker-compose.yml         # Multi-container setup
└── README.md                  # This file
```

## 🚀 Quick Start

### Installation

#### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/team3/nvidia-orchestrator.git
cd nvidia-orchestrator

# Install in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

#### Using pip

```bash
# Install from package
pip install nvidia-orchestrator
```

### Running with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Running Locally

#### Start the API Server

```bash
# Using the CLI
nvidia-orchestrator api --host 0.0.0.0 --port 8000

# Or using Python module
python -m nvidia_orchestrator.api.app

# Or programmatically
from nvidia_orchestrator.api import run_server
run_server()
```

#### Start the Health Monitor

```bash
# Using the CLI
nvidia-orchestrator monitor

# Or using Python module
python -m nvidia_orchestrator.monitoring.health_monitor
```

## 📦 Package Usage

### As a Library

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

# Store events
store.record_event({
    "image": "nginx:alpine",
    "container_id": info["id"],
    "event": "create",
    "status": "running"
})
```

### CLI Commands

```bash
# Show version
nvidia-orchestrator version

# Run API server
nvidia-orchestrator api --host 0.0.0.0 --port 8000

# Run health monitor
nvidia-orchestrator monitor

# Get help
nvidia-orchestrator --help
```

## 🛠️ Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linters
ruff check src/
black --check src/

# Format code
black src/
ruff check --fix src/

# Type checking
mypy src/
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=nvidia_orchestrator --cov-report=html
```

## 📚 API Documentation

The orchestrator provides a REST API for container management. See [docs/README_API.md](docs/README_API.md) for detailed API documentation.

### Key Endpoints

- `GET /health` - Health check
- `GET /containers` - List all containers
- `POST /containers/{imageId}/start` - Start containers
- `POST /containers/{imageId}/stop` - Stop a container
- `DELETE /containers/{idOrName}` - Delete a container
- `GET /containers/instances/{instanceId}/health` - Get container health

## 🐳 Container Management

The system manages Docker containers with:
- **Automatic port mapping** - Detects and maps exposed ports
- **Resource limits** - CPU and memory constraints
- **Health monitoring** - Continuous health checks
- **Event tracking** - PostgreSQL-based event storage
- **Service discovery** - Built-in registry system

See [docs/README_CONTAINER_SYSTEM.md](docs/README_CONTAINER_SYSTEM.md) for details.

## 📊 Health Monitoring

The health monitor runs continuously to:
- Collect CPU, memory, and disk usage metrics
- Store snapshots in PostgreSQL
- Determine health status (healthy/warning/critical/stopped)
- Prune old data based on retention policy

## 🔧 Configuration

Environment variables:

```bash
# PostgreSQL
POSTGRES_URL=postgresql://user:pass@host:5432/db

# Monitoring
HEALTH_INTERVAL_SECONDS=60
HEALTH_RETENTION_DAYS=7

# Logging
LOG_FILE=/app/logs/combined.log

# Service Discovery
REGISTRY_URL=http://registry:8000/registry/endpoints
REGISTRY_API_KEY=your-api-key
```

## 📄 License

MIT License - see LICENSE file for details.

## 👥 Team

Team 3 - NVIDIA Orchestrator Project

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📖 Additional Documentation

- [API Reference](docs/README_API.md)
- [Application Guide](docs/README_APP.md)
- [Container System](docs/README_CONTAINER_SYSTEM.md)





