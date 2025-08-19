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





@router.post("/upload", response_model=DockerUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_docker_image(
    image: UploadFile = File(...),
    image_name: str = Form(..., alias="imageName"),
    inner_port: int = Form(..., alias="innerPort"),
    scaling_type: ScalingType = Form(..., alias="scalingType"),
    min_containers: int = Form(0, alias="minContainers"),
    max_containers: int = Form(0, alias="maxContainers"),
    static_containers: int = Form(0, alias="staticContainers"),
    items_per_container: int = Form(..., alias="itemsPerContainer"),
    payment_limit: float = Form(..., alias="paymentLimit"),
    description: str | None = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a Docker image"""
    logger.info(f"POST /docker/upload - Docker image upload attempt by user: {current_user.email}, image_name: {image_name}")
    
    # Validate file type (case-insensitive)
    filename_lower = (image.filename or "").lower()
    if not filename_lower.endswith(('.tar', '.tar.gz', '.tgz')):
        logger.error(f"POST /docker/upload - Invalid file type: {image.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Docker image files (.tar, .tar.gz, .tgz) are allowed"
        )
    
    # Save file
    file_path = os.path.join(UPLOAD_DIR, f"{current_user.id}_{image.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    # Create database record
    db_image = DockerImage(
        user_id=current_user.id,
        name=image_name,
        image_file_path=file_path,
        inner_port=inner_port,
        scaling_type=scaling_type,
        min_containers=min_containers,
        max_containers=max_containers,
        static_containers=static_containers,
        items_per_container=items_per_container,
        payment_limit=payment_limit,
        description=description,
        status="processing"
    )
    
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    logger.info(f"POST /docker/upload - Docker image uploaded successfully: {image_name}, ID: {db_image.id}")
    
    # Generate URL for the uploaded image
    image_filename = os.path.basename(db_image.image_file_path)
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    image_url = f"{base_url}/docker/images/{image_filename}"
    
    # Send to orchestrator for processing
    await external_client.start_container(str(db_image.id), count=1)
    
    # Sync image to orchestrator's database with URL
    try:
        orchestrator_image_data = {
            "image": f"{image_name}:latest",
            "image_url": image_url,  # URL for orchestrator to download the image
            "min_replicas": min_containers or 1,
            "max_replicas": max_containers or 5,
            "resources": {
                "cpu": "1.0",
                "memory": "512Mi",
                "disk": "10GB"
            },
            "env": {},
            "ports": [{"container": inner_port, "host": inner_port}]
        }
        
        await external_client.sync_image_to_orchestrator(orchestrator_image_data)
        logger.info(f"POST /docker/upload - Image synced to orchestrator database: {image_name}")
    except Exception as e:
        logger.error(f"POST /docker/upload - Failed to sync image to orchestrator database {image_name}: {e}")
        # Don't fail the upload if orchestrator sync is unavailable, just log the error
    
    return DockerUploadResponse(
        image_name=db_image.name,
        file_path=db_image.image_file_path,
        image_url=image_url,
        inner_port=db_image.inner_port,
        scaling_type=db_image.scaling_type,
        min_containers=db_image.min_containers or 0,
        max_containers=db_image.max_containers or 0,
        static_containers=db_image.static_containers or 0,
        items_per_container=db_image.items_per_container,
        payment_limit=db_image.payment_limit,
        description=db_image.description,
    )