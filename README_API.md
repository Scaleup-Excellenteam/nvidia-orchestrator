# API Documentation

## Overview

The FastAPI application provides container orchestration endpoints. All operations are logged and events are stored in PostgreSQL.

## 🚀 Quick Test

```bash
# Start the system
docker-compose up

# Test health endpoint
curl http://localhost:8000/health
```

## 📋 Available Endpoints

### Health Check
```bash
GET /health
```
Returns: `{"ok": true}`

### Container Management

#### Start Containers
```bash
POST /containers/{image}/start
Content-Type: application/json

{
  "count": 2,
  "resources": {
    "cpu_limit": "0.5",
    "memory_limit": "512m"
  },
  "env": {"PORT": "8080"},
  "ports": {"80/tcp": 0}
}
```

#### List Instances
```bash
GET /containers/{image}/instances
```
Returns list of running/stopped containers for an image.

#### Check Health
```bash
GET /containers/instances/{instanceId}/health
```
Returns CPU, memory, disk usage and status.

#### Stop Container
```bash
POST /containers/{image}/stop
Content-Type: application/json

{
  "instanceId": "container_id_here"
}
```

#### Delete Container
```bash
DELETE /containers/{image}
Content-Type: application/json

{
  "instanceId": "container_id_here"
}
```

### Events
```bash
GET /events?image=nginx:alpine&limit=100
```
Returns container lifecycle events.

## 🔧 Request Models

### StartRequest
- `count`: Number of containers to start (≥1)
- `resources`: CPU/memory limits
- `env`: Environment variables
- `ports`: Port mappings

### StopRequest/DeleteRequest
- `instanceId`: Container ID or name

## 📊 Response Format

All endpoints return JSON with consistent error handling:
- **Success**: 200 with data
- **Not Found**: 404 with error details
- **Server Error**: 500 with error details

## 📝 Logging

All API operations are logged to `app/logs/combined.log`:
- Container operations (start/stop/delete)
- Health checks
- Errors and exceptions

## 🧪 Testing

```bash
# Test with curl
curl -X POST http://localhost:8000/containers/nginx:alpine/start \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'

# Check instances
curl http://localhost:8000/containers/nginx:alpine/instances
```
