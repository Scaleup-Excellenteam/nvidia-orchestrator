# Container Management System

## Overview

The container management system handles Docker container lifecycle operations with PostgreSQL event logging and health monitoring.

## 🏗️ Architecture

```
FastAPI (app.py)
    ↓
ContainerManager (container_manager.py)
    ↓
Docker SDK + PostgreSQL Store
```

## 🔧 Core Components

### ContainerManager
- **Purpose**: Manages Docker container operations
- **Features**: Create, start, stop, delete containers
- **Labeling**: All containers tagged with `managed-by` label
- **Resources**: CPU and memory limits support

### PostgresStore
- **Purpose**: Persistent storage for events and health data
- **Tables**: `events`, `desired_images`, `health_snapshots`
- **Auto-init**: Creates schema on first connection

### Health Monitor
- **Purpose**: Collects container health metrics
- **Metrics**: CPU, memory, disk usage
- **Interval**: Configurable (default: 60 seconds)
- **Retention**: Configurable (default: 7 days)

## 🚀 Container Operations

### Creating Containers
```python
# Start a container with resources
summary = manager.create_container(
    image="nginx:alpine",
    env={"PORT": "8080"},
    ports={"80/tcp": 0},  # Auto-assign port
    resources={
        "cpu_limit": "0.5",
        "memory_limit": "512m"
    }
)
```

### Container Lifecycle
1. **Create**: Container started with specified config
2. **Monitor**: Health metrics collected periodically
3. **Events**: All operations logged to PostgreSQL
4. **Cleanup**: Containers can be stopped/deleted

## 📊 Health Monitoring

### Metrics Collected
- **CPU Usage**: Percentage of CPU limit
- **Memory Usage**: Percentage of memory limit  
- **Disk Usage**: Host filesystem usage
- **Status**: healthy/warning/critical/stopped

### Health Check Endpoint
```bash
GET /containers/instances/{instanceId}/health
```

Returns:
```json
{
  "cpu_usage": 25.5,
  "memory_usage": 45.2,
  "disk_usage": 67.8,
  "status": "healthy"
}
```

## 📝 Event Logging

### Event Types
- `create`: Container created
- `start`: Container started
- `stop`: Container stopped
- `remove`: Container deleted

### Event Data
- Container ID and name
- Image name
- Host information
- Port mappings
- Timestamp

## 🔍 Container Discovery

### Label-Based Management
```python
LABEL_KEY = "managed-by"
# All containers tagged with: managed-by=<image_name>
```

### Finding Containers
```python
# List all managed containers
containers = manager.list_managed_containers()

# Find containers for specific image
instances = manager.list_instances_for_image("nginx:alpine")
```

## ⚙️ Configuration

### Environment Variables
- `POSTGRES_URL`: Database connection string
- `HEALTH_INTERVAL_SECONDS`: Health check interval (default: 60)
- `HEALTH_RETENTION_DAYS`: Health data retention (default: 7)
- `LOG_FILE`: Log file path

### Resource Limits
- **CPU**: Accepts "0.5", "500m", "1" format
- **Memory**: Accepts "512m", "1g" format
- **Ports**: Auto-assignment or specific mapping

## 🧪 Testing

### Basic Operations
```bash
# Start container
curl -X POST http://localhost:8000/containers/nginx:alpine/start \
  -d '{"count": 1}'

# Check health
curl http://localhost:8000/containers/instances/{id}/health

# List instances
curl http://localhost:8000/containers/nginx:alpine/instances
```

### Health Monitor
```bash
# Run health monitor standalone
python health_monitor.py
```

## 📋 Current Status

✅ **Working**: Container CRUD operations, health monitoring, event logging  
🔄 **In Progress**: API endpoint alignment, error handling  
📋 **Planned**: Auto-scaling, advanced resource management
