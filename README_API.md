# README: API Documentation & Contracts

This document provides comprehensive API documentation for Team 3's Orchestrator system, including all endpoints, request/response formats, and integration contracts with other teams.

## 🎯 API Overview

**Base URL:** `http://localhost:8000`  
**Content-Type:** `application/json`  
**Authentication:** Currently none (to be implemented)  
**Rate Limiting:** Currently none (to be implemented)

## 📋 API Endpoints Summary

| Method | Endpoint | Purpose | Team Usage |
|--------|----------|---------|-------------|
| `GET` | `/health` | Basic health check | All teams |
| `GET` | `/health/detailed` | Component health status | DevOps, Admin |
| `GET` | `/system/resources` | System resource availability | Load Balancer, Auto-scaling |
| `GET` | `/containers` | List all managed containers | UI, Load Balancer |
| `GET` | `/images` | Show desired state & counts | UI, Billing |
| `GET` | `/containers/{image}/instances` | List instances of image | Load Balancer |
| `GET` | `/containers/instances/{id}/health` | Container health status | Load Balancer, Billing |
| `GET` | `/test/integration` | System integration test | DevOps |
| `POST` | `/containers/{image}/start` | Start new containers | UI, Auto-scaling |
| `POST` | `/containers/{image}/stop` | Stop running containers | UI, Auto-scaling |
| `PUT` | `/containers/{image}/resources` | Update resource limits | UI, Auto-scaling |
| `DELETE` | `/containers/{id}` | Delete containers | UI, Cleanup |
| `POST` | `/registry/endpoints` | Register service endpoint | Service Discovery |
| `PUT` | `/registry/endpoints/{id}/status` | Update endpoint status | Service Discovery |
| `DELETE` | `/registry/endpoints/{id}` | Remove endpoint | Service Discovery |

---

## 🏥 Health & Status Endpoints

### **1. Basic Health Check**

```http
GET /health
```

**Purpose:** Quick health check to verify service is running.

**Response:**
```json
{
  "status": "OK"
}
```

**Use Cases:**
- Load balancer health probes
- Quick service availability check
- Monitoring system basic status

**Team Usage:** All teams

---

### **2. Detailed Health Check**

```http
GET /health/detailed
```

**Purpose:** Comprehensive health check of all system components.

**Response:**
```json
{
  "status": "OK",
  "timestamp": "2025-08-18T18:30:50.883548+00:00",
  "components": {
    "docker": {
      "status": "OK",
      "message": "Connected"
    },
    "postgresql": {
      "status": "OK",
      "message": "Connected"
    },
    "container_manager": {
      "status": "OK",
      "message": "Managing 3 containers"
    },
    "system_resources": {
      "status": "OK",
      "cpu_usage": "15.2%",
      "memory_usage": "45.8%"
    }
  }
}
```

**Status Values:**
- `"OK"` - All components healthy
- `"DEGRADED"` - Some components have issues
- `"ERROR"` - Critical components failed

**Use Cases:**
- Admin dashboard monitoring
- Debugging system issues
- DevOps system validation

**Team Usage:** DevOps, Admin, Monitoring

---

### **3. System Resources**

```http
GET /system/resources
```

**Purpose:** Shows available system resources for scaling decisions.

**Response:**
```json
{
  "system": {
    "cpu": {
      "total_cores": 12,
      "current_usage_percent": 15.2,
      "available_cores": 10.18
    },
    "memory": {
      "total_gb": 15.47,
      "available_gb": 8.42,
      "usage_percent": 45.8
    },
    "disk": {
      "total_gb": 1006.85,
      "free_gb": 753.5,
      "usage_percent": 25.2
    }
  },
  "docker": {
    "managed_containers": 3,
    "running_containers": 3,
    "total_cpu_usage_percent": 12.5,
    "total_memory_usage_mb": 1024.0,
    "average_cpu_per_container": 4.17,
    "average_memory_per_container_mb": 341.33
  }
}
```

**Use Cases:**
- Load balancer scaling decisions
- Auto-scaling algorithms
- Resource planning

**Team Usage:** Load Balancer, Auto-scaling, DevOps

---

## 📦 Container Management Endpoints

### **4. List All Containers**

```http
GET /containers
```

**Purpose:** Shows all containers managed by the orchestrator.

**Response:**
```json
{
  "containers": [
    {
      "id": "abc123def456",
      "name": "nginx-container-1",
      "image": "nginx:alpine",
      "status": "running",
      "ports": {
        "80/tcp": 8080
      },
      "created_at": "2025-08-18T18:00:00Z",
      "resources": {
        "cpu_limit": "0.5",
        "memory_limit": "512m"
      }
    }
  ],
  "total": 1
}
```

**Use Cases:**
- UI dashboard showing all containers
- Load balancer discovering available services
- Billing system counting active containers

**Team Usage:** UI, Load Balancer, Billing

---

### **5. List Image Instances**

```http
GET /containers/{imageId}/instances
```

**Purpose:** Shows all containers running a specific image.

**Path Parameters:**
- `imageId`: Docker image name (e.g., "nginx:alpine")

**Response:**
```json
{
  "instances": [
    {
      "id": "abc123def456",
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

**Use Cases:**
- Load balancer needs to know available instances
- Auto-scaling checking current replica count
- Service discovery finding endpoints

**Team Usage:** Load Balancer, Service Discovery, Auto-scaling

---

### **6. Start Containers**

```http
POST /containers/{imageId}/start
```

**Purpose:** Creates and starts new containers for a specific image.

**Path Parameters:**
- `imageId`: Docker image name (e.g., "nginx:alpine")

**Request Body:**
```json
{
  "count": 2,
  "resources": {
    "cpu_limit": "0.25",
    "memory_limit": "256m"
  }
}
```

**Response:**
```json
{
  "started": [
    "abc123def456",
    "def456ghi789"
  ]
}
```

**Use Cases:**
- UI starting new containers
- Auto-scaling adding replicas
- Manual container deployment

**Team Usage:** UI, Auto-scaling, DevOps

---

### **7. Stop Containers**

```http
POST /containers/{imageId}/stop
```

**Purpose:** Stops running containers.

**Path Parameters:**
- `imageId`: Docker image name

**Request Body:**
```json
{
  "instanceId": "abc123def456"
}
```

**Response:**
```json
{
  "stopped": true
}
```

**Use Cases:**
- UI stopping containers
- Auto-scaling reducing replicas
- Manual container management

**Team Usage:** UI, Auto-scaling, DevOps

---

### **8. Update Container Resources**

```http
PUT /containers/{imageId}/resources
```

**Purpose:** Changes CPU/memory limits for running containers.

**Path Parameters:**
- `imageId`: Docker image name

**Request Body:**
```json
{
  "cpu_limit": "0.5",
  "memory_limit": "512m"
}
```

**Response:**
```json
{
  "updated": [
    "abc123def456",
    "def456ghi789"
  ]
}
```

**Use Cases:**
- UI adjusting resource limits
- Auto-scaling optimizing resources
- Performance tuning

**Team Usage:** UI, Auto-scaling, DevOps

---

### **9. Delete Containers**

```http
DELETE /containers/{idOrName}?force=false
```

**Purpose:** Completely removes containers from the system.

**Path Parameters:**
- `idOrName`: Container ID or name

**Query Parameters:**
- `force`: Force deletion even if running (default: false)

**Response:**
```json
{
  "deleted": true,
  "container_id": "abc123def456",
  "name": "nginx-container-1"
}
```

**Use Cases:**
- UI cleanup actions
- System maintenance
- Resource cleanup

**Team Usage:** UI, DevOps, Cleanup

---

## 🔍 Container Health Endpoints

### **10. Container Health Status**

```http
GET /containers/instances/{instanceId}/health
```

**Purpose:** Shows real-time health status of a specific container.

**Path Parameters:**
- `instanceId`: Container ID

**Response:**
```json
{
  "cpu_usage": 25.5,
  "memory_usage": 45.2,
  "disk_usage": 0.0,
  "status": "healthy",
  "errors": ["cpu_usage_unavailable"]
}
```

**Health Status Values:**
- `"healthy"` - CPU < 75%, Memory < 75%
- `"warning"` - CPU 75-90%, Memory 75-90%
- `"critical"` - CPU > 90%, Memory > 90%
- `"stopped"` - Container not running

**Use Cases:**
- Load balancer health checks
- Billing usage metrics
- Performance monitoring
- Auto-scaling decisions

**Team Usage:** Load Balancer, Billing, Monitoring, Auto-scaling

---

## 🔍 Service Discovery Endpoints

### **11. Register Service Endpoint**

```http
POST /registry/endpoints
```

**Purpose:** Registers a new service endpoint or updates an existing one.

**Request Body:**
```json
{
  "id": "web-service-1",
  "image_id": "nginx:alpine",
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
  "id": "web-service-1",
  "image_id": "nginx:alpine",
  "host": "192.168.1.100",
  "port": 8080,
  "status": "UP",
  "last_heartbeat": "2025-08-18T18:30:50.883548+00:00",
  "caps": {
    "cpu": "0.5",
    "mem": "512m"
  }
}
```

**Use Cases:**
- Services registering themselves
- Load balancer discovering endpoints
- Service mesh integration

**Team Usage:** Service Discovery, Load Balancer

---

### **12. Update Endpoint Status**

```http
PUT /registry/endpoints/{endpoint_id}/status
```

**Purpose:** Updates the status of a registered endpoint.

**Path Parameters:**
- `endpoint_id`: Endpoint identifier

**Request Body:**
```json
{
  "status": "DOWN"
}
```

**Status Values:**
- `"UP"` - Service is available
- `"DOWN"` - Service is unavailable

**Response:** Updated endpoint information

**Use Cases:**
- Services marking themselves unavailable
- Load balancer removing unhealthy endpoints
- Maintenance mode

**Team Usage:** Service Discovery, Load Balancer

---

### **13. Remove Endpoint**

```http
DELETE /registry/endpoints/{endpoint_id}
```

**Purpose:** Removes an endpoint from the registry.

**Path Parameters:**
- `endpoint_id`: Endpoint identifier

**Response:**
```json
{
  "ok": true
}
```

**Use Cases:**
- Services shutting down
- Cleanup of old endpoints
- Service deregistration

**Team Usage:** Service Discovery, Cleanup

---

## 🧪 Testing & Validation Endpoints

### **14. Integration Test**

```http
GET /test/integration
```

**Purpose:** Runs comprehensive system validation tests.

**Response:**
```json
{
  "timestamp": "2025-08-18T18:31:32.732949+00:00",
  "tests": {
    "docker_connection": {
      "status": "PASS",
      "message": "Docker daemon accessible"
    },
    "container_listing": {
      "status": "PASS",
      "message": "Found 3 managed containers"
    },
    "postgresql": {
      "status": "PASS",
      "message": "Database connected"
    },
    "system_resources": {
      "status": "PASS",
      "message": "12 CPU cores, 15.5GB RAM"
    },
    "health_monitoring": {
      "status": "PASS",
      "message": "Health data available: 15 recent records"
    }
  },
  "overall_status": "PASSED"
}
```

**Test Status Values:**
- `"PASS"` - Test successful
- `"FAIL"` - Test failed
- `"WARNING"` - Test passed with warnings

**Use Cases:**
- DevOps system validation
- Debugging system issues
- Pre-deployment testing
- Monitoring system health

**Team Usage:** DevOps, Monitoring, Debugging

---

## 📊 Data Models

### **Request Models**

#### **StartBody**
```json
{
  "count": 1,
  "resources": {
    "cpu_limit": "0.25",
    "memory_limit": "256m",
    "disk_limit": "1g"
  }
}
```

#### **StopBody**
```json
{
  "instanceId": "container-id-here"
}
```

#### **PutResourcesBody**
```json
{
  "cpu_limit": "0.5",
  "memory_limit": "512m",
  "disk_limit": "2g"
}
```

#### **EndpointIn**
```json
{
  "id": "unique-endpoint-id",
  "image_id": "docker-image-name",
  "host": "ip-address-or-hostname",
  "port": 8080,
  "caps": {
    "cpu": "0.5",
    "mem": "512m"
  }
}
```

### **Response Models**

#### **InstancesResponse**
```json
{
  "instances": [
    {
      "id": "container-id",
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

#### **HealthResponse**
```json
{
  "cpu_usage": 25.5,
  "memory_usage": 45.2,
  "disk_usage": 0.0,
  "status": "healthy",
  "errors": ["cpu_usage_unavailable"]
}
```

#### **StartResponse**
```json
{
  "started": ["container-id-1", "container-id-2"]
}
```

---

## 🚨 Error Handling

### **HTTP Status Codes**

- **200 OK** - Request successful
- **400 Bad Request** - Invalid request data
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

### **Error Response Format**

```json
{
  "detail": "Clear explanation of what went wrong"
}
```

### **Common Error Scenarios**

#### **Container Not Found**
```json
{
  "detail": "Instance 'abc123' not found"
}
```

#### **Invalid Resource Limits**
```json
{
  "detail": "Invalid CPU limit format. Expected format: '0.25' or '500m'"
}
```

#### **Docker Connection Failed**
```json
{
  "detail": "Failed to connect to Docker daemon: Connection refused"
}
```

---

## 🔄 Integration Patterns

### **For Team 1 (UI & API)**

#### **Container Dashboard**
```javascript
// Get all containers
const response = await fetch('/containers');
const containers = await response.json();

// Start new container
const startResponse = await fetch('/containers/nginx:alpine/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ count: 1, resources: { cpu_limit: '0.5', memory_limit: '512m' } })
});
```

#### **Health Monitoring**
```javascript
// Check system health
const healthResponse = await fetch('/health/detailed');
const health = await healthResponse.json();

// Monitor specific container
const containerHealth = await fetch(`/containers/instances/${containerId}/health`);
```

### **For Team 2 (Load Balancer)**

#### **Service Discovery**
```javascript
// Get healthy containers for load balancing
const instances = await fetch('/containers/nginx:alpine/instances');
const healthyInstances = instances.filter(i => i.status === 'running');

// Check container health before routing
const health = await fetch(`/containers/instances/${instanceId}/health`);
if (health.status === 'healthy') {
  // Route traffic to this container
}
```

#### **Resource Monitoring**
```javascript
// Check if system can handle more traffic
const resources = await fetch('/system/resources');
if (resources.system.cpu.available_cores > 2) {
  // System can handle more load
}
```

### **For Team 4 (Billing)**

#### **Usage Metrics Collection**
```javascript
// Get all containers for billing
const containers = await fetch('/containers');
const activeContainers = containers.filter(c => c.status === 'running');

// Collect health data for billing
for (const container of activeContainers) {
  const health = await fetch(`/containers/instances/${container.id}/health`);
  // Process billing data
}
```

### **For Team 5 (DevOps)**

#### **System Validation**
```javascript
// Run integration tests
const testResults = await fetch('/test/integration');
if (testResults.overall_status === 'PASSED') {
  // System is healthy
} else {
  // Investigate failures
}
```

#### **Health Monitoring**
```javascript
// Monitor system health
const health = await fetch('/health/detailed');
if (health.status !== 'OK') {
  // Alert DevOps team
}
```

---

## 📈 Performance Considerations

### **Response Times**
- **Health checks**: < 100ms
- **Container operations**: < 2 seconds
- **Health data**: < 500ms
- **System resources**: < 1 second

### **Rate Limiting**
Currently no rate limiting implemented. Consider implementing for production use.

### **Caching**
Health data is cached for 60 seconds. Container lists are real-time.

---

## 🔐 Security Considerations

### **Current Implementation**
- No authentication required
- CORS enabled for web UI
- Docker socket access for container management

### **Production Recommendations**
- Implement API key authentication
- Use HTTPS in production
- Consider Docker-in-Docker for security
- Implement rate limiting
- Add request logging and audit trails

---

## 📝 Summary

**Your API provides:**

✅ **Complete container lifecycle management**  
✅ **Real-time health monitoring**  
✅ **Service discovery and registration**  
✅ **System resource monitoring**  
✅ **Comprehensive testing endpoints**  
✅ **Professional error handling**  
✅ **Clear integration contracts**  

**Every endpoint is designed to work seamlessly with other teams' systems, providing a robust foundation for container orchestration!** 🎉

**Ready for tomorrow's integration testing!** 🚀
