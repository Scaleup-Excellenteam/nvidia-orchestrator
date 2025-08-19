# README: app.py - FastAPI Application Documentation

This document explains every function in `app.py`, the main FastAPI application for Team 3's Orchestrator system.

## 🏗️ File Overview

**`app.py`** is the heart of your system - it's the main API server that:
- Handles all HTTP requests from other teams
- Manages container lifecycle operations
- Provides health monitoring and system status
- Enables service discovery and registration

## 📋 Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [Health Endpoints](#health-endpoints)
3. [Container Management](#container-management)
4. [System Monitoring](#system-monitoring)
5. [Service Discovery](#service-discovery)
6. [Testing & Validation](#testing--validation)
7. [Helper Functions](#helper-functions)

---

## 🔧 Setup & Configuration

### **FastAPI App Initialization**
```python
app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")
```
**What it does:** Creates the main FastAPI application with title and version.

### **CORS Middleware**
```python
app.add_middleware(CORSMiddleware, ...)
```
**What it does:** Allows web browsers to make requests to your API from different domains (needed for Team 1's UI).

### **Global Exception Handler**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
```
**What it does:** Catches any unexpected errors and returns a nice error message instead of crashing the system.

---

## 🏥 Health Endpoints

### **Basic Health Check**
```python
@app.get("/health")
def health():
    return {"status": "OK"}
```
**What it does:** Simple endpoint that just says "I'm alive!" - used by other teams to check if your service is running.

**When to use:** Quick health check, load balancer health probes.

### **Detailed Health Check**
```python
@app.get("/health/detailed")
def health_detailed():
```
**What it does:** Comprehensive health check that tests every component:
- ✅ Docker connection
- ✅ PostgreSQL database
- ✅ Container manager
- ✅ System resources

**Returns:** Detailed status of each component with helpful messages.

**When to use:** Debugging issues, monitoring system health, admin dashboard.

---

## 📦 Container Management

### **List All Containers**
```python
@app.get("/containers")
def get_all_containers():
```
**What it does:** Shows all containers your system is managing.

**Returns:** List of containers with:
- Container ID and name
- Image name
- Current status (running/stopped)
- Port mappings
- Resource limits

**When to use:** Team 1 (UI) needs to show all containers, Team 2 (Load Balancer) needs to know what's available.

### **List Instances for Image**
```python
@app.get("/containers/{imageId}/instances")
def get_instances(imageId: str):
```
**What it does:** Shows all containers running a specific image (e.g., all nginx containers).

**Returns:** List of instances with status and endpoint information.

**When to use:** Team 2 (Load Balancer) needs to know how many instances of an image are available.

### **Start Containers**
```python
@app.post("/containers/{imageId}/start")
def start_image(imageId: str, body: StartBody):
```
**What it does:** Creates and starts new containers for a specific image.

**Parameters:**
- `imageId`: Docker image name (e.g., "nginx:alpine")
- `body.count`: How many containers to start
- `body.resources`: CPU/memory limits

**Returns:** List of container IDs that were started.

**When to use:** Team 1 (UI) wants to start new containers, auto-scaling needs more instances.

### **Stop Containers**
```python
@app.post("/containers/{imageId}/stop")
def stop_image_instance(imageId: str, body: StopBody):
```
**What it does:** Stops a running container.

**Parameters:**
- `body.instanceId`: Container ID to stop

**Returns:** Confirmation that container was stopped.

**When to use:** Team 1 (UI) wants to stop containers, auto-scaling needs to reduce instances.

### **Delete Containers**
```python
@app.delete("/containers/{idOrName}")
def delete_container_by_id(idOrName: str, force: bool = False):
```
**What it does:** Completely removes a container from the system.

**Parameters:**
- `idOrName`: Container ID or name
- `force`: Force deletion even if running

**Returns:** Confirmation that container was deleted.

**When to use:** Cleanup, removing old containers, Team 1 (UI) delete action.

### **Update Container Resources**
```python
@app.put("/containers/{imageId}/resources")
def update_resources(imageId: str, body: PutResourcesBody):
```
**What it does:** Changes CPU/memory limits for running containers.

**Parameters:**
- `body.cpu_limit`: New CPU limit
- `body.memory_limit`: New memory limit

**Returns:** List of container IDs that were updated.

**When to use:** Team 1 (UI) wants to change resource limits, auto-scaling adjustments.

---

## 📊 System Monitoring

### **System Resources**
```python
@app.get("/system/resources")
def get_system_resources():
```
**What it does:** Shows available system resources for scaling decisions.

**Returns:**
- **CPU**: Total cores, current usage, available cores
- **Memory**: Total GB, available GB, usage percentage
- **Disk**: Total GB, free GB, usage percentage
- **Docker**: Container usage statistics

**When to use:** Team 2 (Load Balancer) needs to know if system can handle more containers, auto-scaling decisions.

### **Container Health**
```python
@app.get("/containers/instances/{instanceId}/health")
def instance_health(instanceId: str):
```
**What it does:** Checks the health of a specific container.

**Returns:**
- **CPU usage**: Percentage of allocated CPU
- **Memory usage**: Percentage of allocated memory
- **Status**: healthy/warning/critical/stopped
- **Errors**: Any issues with metrics collection

**When to use:** Team 2 (Load Balancer) needs to know which containers are healthy, Team 4 (Billing) needs usage data.

---

## 🔍 Service Discovery

### **Register Endpoint**
```python
@app.post("/registry/endpoints")
def register_or_update_endpoint(body: EndpointIn):
```
**What it does:** Registers a new service endpoint or updates an existing one.

**Parameters:**
- `body.id`: Unique endpoint identifier
- `body.image_id`: Docker image name
- `body.host`: IP address or hostname
- `body.port`: Service port number

**Returns:** Saved endpoint with timestamp.

**When to use:** Other teams need to register their services, load balancer needs to know about new endpoints.

### **Update Endpoint Status**
```python
@app.put("/registry/endpoints/{endpoint_id}/status")
def set_endpoint_status(endpoint_id: str, status: StatusEnum):
```
**What it does:** Updates the status of a registered endpoint (UP/DOWN).

**Parameters:**
- `status`: UP or DOWN

**Returns:** Updated endpoint information.

**When to use:** Services want to mark themselves as unavailable, load balancer needs to know endpoint status.

### **Delete Endpoint**
```python
@app.delete("/registry/endpoints/{endpoint_id}")
def delete_endpoint(endpoint_id: str):
```
**What it does:** Removes an endpoint from the registry.

**Returns:** Confirmation of deletion.

**When to use:** Services shutting down, cleanup of old endpoints.

---

## 🧪 Testing & Validation

### **Integration Test**
```python
@app.get("/test/integration")
def test_integration():
```
**What it does:** Runs a comprehensive test of all system components.

**Tests:**
1. Docker connection
2. Container listing
3. PostgreSQL connection
4. System resources
5. Health monitoring

**Returns:** Detailed test results with pass/fail status.

**When to use:** Team 5 (DevOps) validation, debugging system issues, ensuring everything works.

---

## 🚀 Startup & Registration

### **Startup Event Handler**
```python
@app.on_event("startup")
async def do_register():
```
**What it does:** Runs when your service starts up.

**What happens:**
1. **Validates all components** (Docker, PostgreSQL, Container Manager)
2. **Registers with service discovery** (if configured)
3. **Logs startup status** with emojis and clear messages

**When it runs:** Every time your container starts or restarts.

### **Startup Validation**
```python
async def validate_startup() -> Dict[str, Any]:
```
**What it does:** Checks that all critical components are working.

**Checks:**
- ✅ Docker connection
- ✅ PostgreSQL connection
- ✅ Container manager
- ✅ System resources

**Returns:** Validation results with success/error status.

---

## 🛠️ Helper Functions

### **Fetch UI User**
```python
def _fetch_ui_user() -> Dict[str, Optional[str]]:
```
**What it does:** Gets user information from Team 1's UI (for authentication).

**Returns:** User ID, name, and email (or None if UI is unavailable).

**When to use:** Adding user context to operations, logging who performed actions.

### **Instance View Helper**
```python
def _instance_view(s: Dict[str, Any]) -> Dict[str, Any]:
```
**What it does:** Formats container information for API responses.

**Returns:** Clean, standardized container information.

**When to use:** Making sure all endpoints return data in the same format.

### **Health URL Helper**
```python
def _health_url() -> str:
```
**What it does:** Creates the URL for your service's health endpoint.

**Returns:** Full health check URL.

**When to use:** Service discovery registration, telling other teams how to check your health.

---

## 🔄 Data Models

### **Request Models**
- **`StartBody`**: What to send when starting containers
- **`StopBody`**: What to send when stopping containers
- **`PutResourcesBody`**: What to send when updating resources

### **Response Models**
- **`InstancesResponse`**: Container instance information
- **`HealthResponse`**: Container health status
- **`StartResponse`**: Confirmation of started containers

### **Service Discovery Models**
- **`EndpointIn`**: Service endpoint registration
- **`EndpointOut`**: Service endpoint information
- **`StatusEnum`**: UP/DOWN status values

---

## 🎯 How Other Teams Use This

### **Team 1 (UI & API)**
- **`/containers`** - Show all containers
- **`/containers/{image}/start`** - Start new containers
- **`/containers/{image}/stop`** - Stop containers
- **`/health/detailed`** - Monitor system health

### **Team 2 (Load Balancer)**
- **`/containers/instances/{id}/health`** - Check container health
- **`/registry/endpoints`** - Discover available services
- **`/system/resources`** - Know if system can handle more traffic

### **Team 4 (Billing)**
- **`/containers/instances/{id}/health`** - Get usage metrics
- **`/containers`** - Count running containers
- **`/system/resources`** - Monitor overall system usage

### **Team 5 (DevOps)**
- **`/test/integration`** - Validate system integration
- **`/health/detailed`** - Debug component issues
- **All endpoints** - Test complete functionality

---

## 🚨 Error Handling

### **What Happens When Things Go Wrong**
1. **Container not found** → Returns 404 with clear message
2. **Docker connection lost** → Returns 500 with error details
3. **Database unavailable** → Returns 500 with connection error
4. **Invalid request data** → Returns 400 with validation error

### **Error Response Format**
```json
{
  "detail": "Clear explanation of what went wrong"
}
```

---

## 📝 Summary

**`app.py` is your system's command center** - it:
- ✅ **Handles all requests** from other teams
- ✅ **Manages containers** (start, stop, delete, monitor)
- ✅ **Provides health checks** for system monitoring
- ✅ **Enables service discovery** for load balancing
- ✅ **Handles errors gracefully** with clear messages
- ✅ **Validates startup** to ensure everything works

**Every function has a clear purpose** and is designed to work with other teams' systems. Your API is production-ready and follows professional standards! 🎉
