# NVIDIA Orchestrator API Documentation

## Overview
The NVIDIA Orchestrator API provides container management, health monitoring, and service registry functionality.

**API Version:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**OpenAPI Version:** 3.1.0

---

## 🔗 Quick Links

- **📖 Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **📋 ReDoc Interface:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **📄 Raw OpenAPI Spec:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 📋 API Endpoints

### 🏥 Health & Monitoring

#### `GET /health`
Basic health check endpoint.

**Response:**
```json
{
  "status": "OK"
}
```

#### `GET /health/detailed`
Comprehensive system health check.

**Response:**
```json
{
  "status": "OK",
  "timestamp": "2025-01-01T12:00:00Z",
  "components": {
    "docker": {"status": "OK", "message": "Connected"},
    "postgresql": {"status": "OK", "message": "Connected"},
    "container_manager": {"status": "OK", "message": "Managing 3 containers"},
    "system_resources": {
      "status": "OK",
      "cpu_usage": "16.0%",
      "memory_usage": "26.3%"
    }
  }
}
```

#### `GET /test/integration`
System integration validation test.

**Response:**
```json
{
  "timestamp": "2025-01-01T12:00:00Z",
  "tests": {
    "docker_connection": {"status": "PASS", "message": "Docker daemon accessible"},
    "container_listing": {"status": "PASS", "message": "Found 3 managed containers"},
    "postgresql": {"status": "PASS", "message": "Database connected"},
    "system_resources": {"status": "PASS", "message": "20 CPU cores, 31.6GB RAM"},
    "health_monitoring": {"status": "PASS", "message": "Health data available: 5 recent records"}
  },
  "overall_status": "PASSED"
}
```

#### `GET /system/resources`
Get available system resources for scaling decisions.

**Response:**
```json
{
  "system": {
    "cpu": {
      "total_cores": 20,
      "current_usage_percent": 16.0,
      "available_cores": 16.8
    },
    "memory": {
      "total_gb": 31.6,
      "available_gb": 23.3,
      "usage_percent": 26.3
    },
    "disk": {
      "total_gb": 500.0,
      "free_gb": 350.0,
      "usage_percent": 30.0
    }
  },
  "docker": {
    "containers_running": 3,
    "total_cpu_usage": 1.2,
    "total_memory_usage_mb": 1024
  }
}
```

---

### 🐳 Container Management

#### `GET /images`
Get all images with desired state and current running counts.

**Response:**
```json
{
  "images": [
    {
      "image": "nginx:alpine",
      "desired_count": 3,
      "current_running": 2,
      "total_instances": 3,
      "resources": {
        "cpu_limit": "0.5",
        "memory_limit": "512m"
      }
    }
  ]
}
```

#### `POST /start/container`
Start or reuse a container with specified resources.

**Request:**
```json
{
  "count": 1,
  "resources": {
    "image": "nginx:alpine",
    "memory_limit": "512m",
    "cpu_limit": "0.5"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "action": "created",
  "image": "nginx:alpine",
  "container_id": "abc123def456",
  "name": "container-abc123def456",
  "status": "running",
  "ports": {}
}
```

#### `GET /containers`
List all managed containers with status and port bindings.

**Response:**
```json
{
  "containers": [
    {
      "id": "abc123def456",
      "name": "my-container",
      "image": "nginx:alpine",
      "status": "running",
      "ports": {
        "80/tcp": "8080"
      },
      "created_at": "2025-01-01T12:00:00Z",
      "resources": {
        "cpu_limit": "0.5",
        "memory_limit": "512m"
      }
    }
  ],
  "total": 1
}
```

#### `GET /containers/{imageId}/instances`
Get all instances for a specific image.

**Parameters:**
- `imageId` (string): The image identifier

**Response:**
```json
{
  "instances": [
    {
      "id": "container123",
      "status": "running",
      "endpoint": "http://localhost:8080",
      "resources": {
        "cpu_limit": "0.5",
        "memory_limit": "512m"
      }
    }
  ]
}
```

#### `GET /containers/instances/{instanceId}/health`
Get health metrics for a specific container instance.

**Parameters:**
- `instanceId` (string): The container instance identifier

**Response:**
```json
{
  "cpu_usage": 25.5,
  "memory_usage": 45.2,
  "disk_usage": 0.0,
  "status": "healthy",
  "errors": null
}
```

**Status Values:**
- `healthy` - Container is operating normally
- `warning` - CPU/Memory usage is high (75-90%)
- `critical` - CPU/Memory usage is very high (>90%)
- `stopped` - Container is not running

#### `POST /containers/{imageId}/start`
Start new containers for a specific image.

**Parameters:**
- `imageId` (string): The image identifier

**Request:**
```json
{
  "count": 2,
  "resources": {
    "cpu_limit": "0.5",
    "memory_limit": "512m",
    "disk_limit": "10g"
  }
}
```

**Response:**
```json
{
  "started": ["container_id_1", "container_id_2"]
}
```

#### `POST /containers/{imageId}/stop`
Stop a container instance.

**Parameters:**
- `imageId` (string): The image identifier

**Request:**
```json
{
  "instanceId": "container123"
}
```

**Response:**
```json
{
  "stopped": true
}
```

#### `DELETE /containers/{idOrName}`
Delete a container by ID or name.

**Parameters:**
- `idOrName` (string): Container ID or name
- `force` (boolean, optional): Force deletion

**Response:**
```json
{
  "deleted": true,
  "container_id": "container123",
  "name": "container123"
}
```

#### `PUT /containers/{imageId}/resources`
Update resource limits for all containers of an image.

**Parameters:**
- `imageId` (string): The image identifier

**Request:**
```json
{
  "cpu_limit": "1.0",
  "memory_limit": "1024m",
  "disk_limit": "20g"
}
```

**Response:**
```json
{
  "updated": ["container_id_1", "container_id_2"]
}
```

---

### 📡 Service Registry

#### `POST /registry/endpoints`
Register or update a service endpoint.

**Request:**
```json
{
  "id": "my-service-1",
  "image_id": "my-service:latest",
  "host": "192.168.1.100",
  "port": 8080,
  "caps": {
    "cpu": "0.5",
    "mem": "512m"
  }
}
```

**Response:**
```json
{
  "id": "my-service-1",
  "image_id": "my-service:latest",
  "host": "192.168.1.100",
  "port": 8080,
  "caps": {
    "cpu": "0.5",
    "mem": "512m"
  },
  "status": "UP",
  "last_heartbeat": "2025-01-01T12:00:00Z"
}
```

#### `DELETE /registry/endpoints/{endpoint_id}`
Delete a registered endpoint.

**Parameters:**
- `endpoint_id` (string): The endpoint identifier

**Response:**
```json
{
  "ok": true
}
```

#### `PUT /registry/endpoints/{endpoint_id}/status`
Update endpoint status.

**Parameters:**
- `endpoint_id` (string): The endpoint identifier
- `status` (enum): Either "UP" or "DOWN"

**Response:**
```json
{
  "id": "my-service-1",
  "image_id": "my-service:latest",
  "host": "192.168.1.100",
  "port": 8080,
  "caps": {
    "cpu": "0.5",
    "mem": "512m"
  },
  "status": "DOWN",
  "last_heartbeat": "2025-01-01T12:05:00Z"
}
```

---

## 📝 Data Models

### StartBody
```json
{
  "count": 1,                    // Optional, default: 1
  "resources": {                 // Optional
    "cpu_limit": "string",       // e.g., "0.5"
    "memory_limit": "string",    // e.g., "512m"
    "disk_limit": "string"       // e.g., "10g"
  }
}
```

### InstanceResources
```json
{
  "cpu_limit": "string",         // Optional
  "memory_limit": "string",      // Optional
  "disk_limit": "string"         // Optional
}
```

### EndpointIn
```json
{
  "id": "string",                // Required: Unique endpoint ID
  "image_id": "string",          // Required: Image identifier
  "host": "string",              // Required: Host/IP address
  "port": 8080,                  // Required: Port number (1-65535)
  "caps": {                      // Optional
    "cpu": "string",             // e.g., "0.5"
    "mem": "string"              // e.g., "512m"
  }
}
```

### HealthResponse
```json
{
  "cpu_usage": 25.5,             // CPU usage percentage
  "memory_usage": 45.2,          // Memory usage percentage
  "disk_usage": 0.0,             // Disk usage percentage
  "status": "healthy",           // Status enum
  "errors": ["string"]           // Optional array of error messages
}
```

---

## 🚀 Usage Examples

### Start a new container
```bash
curl -X POST http://localhost:8000/containers/nginx:alpine/start \
  -H "Content-Type: application/json" \
  -d '{
    "count": 1,
    "resources": {
      "memory_limit": "256m",
      "cpu_limit": "0.25"
    }
  }'
```

### Check container health
```bash
curl http://localhost:8000/containers/instances/container123/health
```

### List all containers
```bash
curl http://localhost:8000/containers
```

### Register a service endpoint
```bash
curl -X POST http://localhost:8000/registry/endpoints \
  -H "Content-Type: application/json" \
  -d '{
    "id": "web-service-1",
    "image_id": "nginx:alpine",
    "host": "192.168.1.100",
    "port": 80,
    "caps": {
      "cpu": "0.5",
      "mem": "256m"
    }
  }'
```

### Get system resources
```bash
curl http://localhost:8000/system/resources
```

---

## 🔧 Error Responses

All endpoints may return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `404` - Resource Not Found
- `422` - Validation Error
- `500` - Internal Server Error

**Validation Error Format:**
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 🛠️ Development

### Running the API
```bash
# Using Docker Compose (recommended)
docker-compose -f docker-compose.dev.yml up -d

# Direct Python execution
python -m uvicorn nvidia_orchestrator.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Environment Variables
- `POSTGRES_URL`: PostgreSQL connection string
- `LOG_FILE`: Path to log file
- `HEALTH_INTERVAL_SECONDS`: Health check interval
- `REGISTRY_URL`: Service registry URL (optional)
- `REGISTRY_API_KEY`: Service registry API key (optional)

### CORS Configuration
The API is configured to accept requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

---

## 📊 System Requirements

- **Python:** 3.11+
- **Docker:** Latest version
- **PostgreSQL:** 15+ (provided via Docker Compose)
- **System Resources:** Minimum 2GB RAM, 2 CPU cores

---

## 🎯 Service Health

The API provides comprehensive health monitoring:
- Docker daemon connectivity
- PostgreSQL database connection
- Container management functionality
- System resource availability
- Health data persistence

Access health information via:
- Basic: `GET /health`
- Detailed: `GET /health/detailed`
- Integration Test: `GET /test/integration`

---

*Last Updated: $(date)*
*API Version: 1.0.0*
*Generated from: NVIDIA Orchestrator API* 