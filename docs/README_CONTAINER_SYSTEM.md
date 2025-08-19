# README: Container Management System

This document explains how the container management system works in Team 3's Orchestrator.

## 🏗️ System Overview

The container management system is responsible for:
- **Creating and managing Docker containers**
- **Monitoring container health and performance**
- **Managing resource limits (CPU, memory)**
- **Handling container lifecycle operations**
- **Integrating with PostgreSQL for persistence**

## 📋 Core Components

### **1. Container Manager (`container_manager.py`)**
The main class that handles all Docker operations.

### **2. Health Monitor (`health_monitor.py`)**
Background process that continuously monitors container health.

### **3. PostgreSQL Store (`postgres_store.py`)**
Database layer for storing events and health data.

---

## 🔧 Container Manager (`container_manager.py`)

### **Class: `ContainerManager`**

#### **Initialization**
```python
def __init__(self):
    # Creates Docker client connection
    # Initializes PostgreSQL store
    # Sets up container labeling system
```

**What it does:** Sets up connections to Docker and PostgreSQL, prepares for container management.

#### **Container Creation**
```python
def create_container(self, image, env=None, ports=None, resources=None):
```

**What it does:** Creates and starts a new Docker container.

**Parameters:**
- `image`: Docker image name (e.g., "nginx:alpine")
- `env`: Environment variables for the container
- `ports`: Port mappings (container_port: host_port)
- `resources`: CPU and memory limits

**Returns:** Container information including ID, name, and port mappings.

**Example:**
```python
info = manager.create_container(
    image="nginx:alpine",
    env={"DEBUG": "true"},
    ports={"80/tcp": 8080},
    resources={"cpu_limit": "0.5", "memory_limit": "512m"}
)
```

#### **Container Lifecycle Operations**

##### **Start Container**
```python
def start_container(self, name_or_id):
```
**What it does:** Starts a stopped container.

##### **Stop Container**
```python
def stop_container(self, name_or_id, timeout=10):
```
**What it does:** Stops a running container gracefully.

##### **Delete Container**
```python
def delete_container(self, name_or_id, force=False):
```
**What it does:** Completely removes a container from the system.

#### **Container Discovery**

##### **List Managed Containers**
```python
def list_managed_containers(self):
```
**What it does:** Returns all containers managed by this orchestrator.

**Returns:** List of container summaries with status, ports, and resources.

##### **List Instances for Image**
```python
def list_instances_for_image(self, image):
```
**What it does:** Returns all containers running a specific image.

**Use case:** Load balancer needs to know how many instances of an image are available.

#### **Resource Management**

##### **Update Resources**
```python
def update_resources_for_image(self, image, cpu_limit=None, memory_limit=None):
```
**What it does:** Changes CPU/memory limits for running containers.

**Parameters:**
- `cpu_limit`: New CPU limit (e.g., "0.25" for 25% of one core)
- `memory_limit`: New memory limit (e.g., "256m" for 256 megabytes)

##### **Register Desired State**
```python
def register_desired_state(self, image, min_replicas=1, max_replicas=1, resources=None):
```
**What it does:** Sets the desired number of containers for an image.

**Parameters:**
- `min_replicas`: Minimum number of containers to keep running
- `max_replicas`: Maximum number of containers allowed
- `resources`: Default resource limits for new containers

#### **Container Health**

##### **Get Container Stats**
```python
def container_stats(self, name_or_id):
```
**What it does:** Returns real-time performance metrics for a container.

**Returns:** CPU usage, memory usage, network I/O, and disk I/O.

---

## 📊 Health Monitor (`health_monitor.py`)

### **Purpose**
Continuously monitors the health of all managed containers and stores the data in PostgreSQL.

### **How It Works**

#### **Health Collection Loop**
```python
def run_forever():
    while True:
        sample_once(manager, store)
        time.sleep(INTERVAL_SEC)
```

**What it does:** Runs every 60 seconds (configurable) to collect health data.

#### **Health Metrics Collected**

##### **CPU Usage**
```python
def _cpu_percent(stats):
```
**What it does:** Calculates CPU usage percentage from Docker stats.

**Returns:** CPU usage as a percentage (0.0 to 100.0).

##### **Memory Usage**
```python
def _mem_percent(stats):
```
**What it does:** Calculates memory usage percentage from Docker stats.

**Returns:** Memory usage as a percentage (0.0 to 100.0).

##### **Disk Usage**
```python
def _disk_percent():
```
**What it does:** Calculates system disk usage percentage.

**Returns:** Disk usage as a percentage (0.0 to 100.0).

#### **Health Status Classification**
```python
def _status(server_running, cpu, mem):
```
**What it does:** Classifies container health based on metrics.

**Status Levels:**
- **🟢 Healthy**: CPU < 75%, Memory < 75%
- **🟡 Warning**: CPU 75-90%, Memory 75-90%
- **🔴 Critical**: CPU > 90%, Memory > 90%
- **⚫ Stopped**: Container not running

### **Data Persistence**
All health data is stored in PostgreSQL for:
- **Historical analysis**
- **Billing calculations**
- **Performance trending**
- **Debugging issues**

---

## 🗄️ PostgreSQL Store (`postgres_store.py`)

### **Purpose**
Provides persistent storage for container events and health data.

### **Database Tables**

#### **1. `desired_images`**
Stores the desired state for each image.

**Columns:**
- `image`: Docker image name (primary key)
- `min_replicas`: Minimum number of containers
- `max_replicas`: Maximum number of containers
- `resources`: JSON with CPU/memory limits
- `env`: JSON with environment variables
- `ports`: JSON with port mappings
- `updated_at`: Last update timestamp

#### **2. `events`**
Logs all container lifecycle events.

**Columns:**
- `id`: Unique event ID
- `image`: Docker image name
- `container_id`: Container identifier
- `name`: Container name
- `host`: Host machine name
- `ports`: JSON with port mappings
- `status`: Container status
- `event`: Event type (create, start, stop, remove)
- `ts`: Event timestamp

#### **3. `health_snapshots`**
Stores container health data over time.

**Columns:**
- `id`: Unique snapshot ID
- `image`: Docker image name
- `container_id`: Container identifier
- `name`: Container name
- `host`: Host machine name
- `cpu_usage`: CPU usage percentage
- `memory_usage`: Memory usage percentage
- `disk_usage`: Disk usage percentage
- `status`: Health status (healthy, warning, critical, stopped)
- `ts`: Snapshot timestamp

### **Key Methods**

#### **Store Desired State**
```python
def upsert_desired(self, image, doc):
```
**What it does:** Saves or updates the desired state for an image.

#### **Record Events**
```python
def record_event(self, payload):
```
**What it does:** Logs container lifecycle events.

#### **Store Health Data**
```python
def record_health_snapshot(self, payload):
```
**What it does:** Saves container health metrics.

#### **Retrieve Data**
```python
def list_desired(self):
def list_events(self, image=None, limit=100):
def list_recent_health(self, image=None, container_id=None, limit=100):
```

---

## 🔄 Container Lifecycle Flow

### **1. Container Creation**
```
1. API receives start request
2. ContainerManager creates Docker container
3. Container gets "managed-by" label
4. Event logged to PostgreSQL
5. Health monitor begins collecting metrics
6. Container appears in /containers endpoint
```

### **2. Container Monitoring**
```
1. Health monitor runs every 60 seconds
2. Collects CPU, memory, disk usage
3. Classifies health status
4. Stores data in PostgreSQL
5. Updates container health endpoints
```

### **3. Container Scaling**
```
1. API receives scaling request
2. ContainerManager adjusts replica count
3. Starts/stops containers as needed
4. Updates desired state in database
5. Health monitor tracks new containers
```

### **4. Container Cleanup**
```
1. API receives delete request
2. ContainerManager stops container
3. Removes container from Docker
4. Logs removal event
5. Health monitor stops collecting data
```

---

## 🏷️ Container Labeling System

### **Purpose**
All containers managed by this system get a special label to identify them.

### **Label Format**
```python
LABEL_KEY = "managed-by"
labels = {LABEL_KEY: image_name}
```

**Example:**
```bash
docker run --label "managed-by=nginx:alpine" nginx:alpine
```

### **Benefits**
- **Easy identification** of managed containers
- **Cleanup operations** can target specific containers
- **Health monitoring** only tracks relevant containers
- **Integration** with other Docker tools

---

## 📈 Resource Management

### **CPU Limits**
```python
# Convert fractional CPU to nano_cpus
nano_cpus = int(float(cpu_limit) * 1_000_000_000)
```

**Examples:**
- `"0.25"` → 25% of one CPU core
- `"1.0"` → One full CPU core
- `"2.5"` → Two and a half CPU cores

### **Memory Limits**
```python
# Standard Docker memory format
resources = {"mem_limit": "512m"}  # 512 megabytes
resources = {"mem_limit": "1g"}    # 1 gigabyte
```

### **Port Mapping**
```python
# Container port to host port mapping
ports = {
    "80/tcp": 8080,    # Container port 80 → Host port 8080
    "443/tcp": None    # Container port 443 → Random host port
}
```

---

## 🚨 Error Handling

### **Docker Connection Issues**
```python
def _ensure_docker_client(self):
    try:
        self.client.ping()
    except Exception:
        self._init_docker_client()  # Reconnect automatically
```

### **Container Not Found**
```python
try:
    container = self._get_by_name_or_id(name_or_id)
except NotFound:
    return {"ok": False, "error": "not-found"}
```

### **Resource Update Failures**
```python
try:
    container.update(**params)
    updated.append(container.id)
except Exception:
    continue  # Skip failed updates, continue with others
```

---

## 🔍 Debugging & Monitoring

### **View Managed Containers**
```bash
docker ps --filter "label=managed-by"
```

### **Check Container Logs**
```bash
docker logs <container_id>
```

### **Monitor Health Data**
```bash
# Check recent health data
curl http://localhost:8000/containers/instances/<id>/health

# View system resources
curl http://localhost:8000/system/resources
```

### **Database Queries**
```sql
-- View all managed containers
SELECT * FROM events WHERE event = 'create';

-- Check container health over time
SELECT * FROM health_snapshots WHERE container_id = '<id>' ORDER BY ts DESC;

-- See desired state
SELECT * FROM desired_images;
```

---

## 🎯 Integration Points

### **For Team 1 (UI & API)**
- **Container listing** via `/containers` endpoint
- **Container operations** via start/stop/delete endpoints
- **Resource management** via update endpoints

### **For Team 2 (Load Balancer)**
- **Health data** via health endpoints
- **Container discovery** via instances endpoints
- **Resource availability** via system resources endpoint

### **For Team 4 (Billing)**
- **Usage metrics** via health endpoints
- **Container counts** via containers endpoint
- **Historical data** via database

---

## 📝 Summary

**The container management system provides:**

✅ **Complete container lifecycle management**  
✅ **Real-time health monitoring**  
✅ **Resource limit enforcement**  
✅ **Persistent data storage**  
✅ **Automatic error recovery**  
✅ **Professional logging and events**  

**It's designed to work seamlessly with other teams' systems and provides all the functionality needed for a production container orchestration platform!** 🎉
