# Team 3 - NVIDIA Orchestrator

A production-ready container orchestration system built with FastAPI, Docker, and PostgreSQL. This system provides lightweight Kubernetes-like functionality for managing containers, monitoring health, and enabling service discovery.

## 🎯 Project Overview

This system is a lightweight alternative to Kubernetes for running and managing containers. It allows customers to:
- Upload and manage Docker images
- Run containers with resource limits
- Monitor container health in real-time
- Balance load across containers
- Discover services automatically
- Handle billing and usage tracking

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Team 1 - UI   │    │ Team 2 - Load  │    │ Team 4 -       │
│   & API         │◄──►│ Balancer &      │◄──►│ Billing        │
│                 │    │ Service Disc.   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TEAM 3 - ORCHESTRATOR                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   FastAPI App   │  │ Container Mgr   │  │ Health Monitor  │ │
│  │   (app.py)      │  │ (container_     │  │ (health_        │ │
│  │                 │  │  manager.py)    │  │  monitor.py)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ PostgreSQL      │  │ Docker Engine   │                      │
│  │ Store           │  │ Integration     │                      │
│  │ (postgres_      │  │                 │                      │
│  │  store.py)      │  └─────────────────┘                      │
│  └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker Desktop running
- Port 8000 available
- Python 3.11+ (for local testing)

### 1. Start the System
```bash
docker-compose up -d
```

### 2. Wait for Startup
```bash
docker-compose logs -f api
```
Look for: `🎉 All critical components validated successfully!`

### 3. Test the System
```bash
python test_system.py
```
Expected: `🎉 All tests passed! Your system is ready for tomorrow!`

## 📋 Core Components

### **1. FastAPI Application (`app.py`)**
- **Main API server** handling all HTTP requests
- **Service discovery** registration and health checks
- **Container lifecycle** management endpoints
- **System monitoring** and resource reporting

### **2. Container Manager (`container_manager.py`)**
- **Docker integration** for container operations
- **Resource management** (CPU, memory limits)
- **Container lifecycle** (create, start, stop, delete)
- **Health monitoring** integration

### **3. Health Monitor (`health_monitor.py`)**
- **Background process** collecting container metrics
- **Real-time monitoring** of CPU, memory, disk usage
- **Health status classification** (healthy, warning, critical)
- **Database persistence** for historical data

### **4. PostgreSQL Store (`postgres_store.py`)**
- **Event logging** for all container operations
- **Health snapshots** for monitoring data
- **Desired state** management for containers
- **Data persistence** for billing and analytics

## 🔧 API Endpoints

### **Health & Status**
- `GET /health` - Basic service health
- `GET /health/detailed` - Component-by-component health
- `GET /system/resources` - Available system resources

### **Container Management**
- `GET /containers` - List all managed containers
- `GET /images` - Show desired state and container counts
- `POST /containers/{image}/start` - Start containers
- `POST /containers/{image}/stop` - Stop containers
- `DELETE /containers/{id}` - Delete containers

### **Container Health**
- `GET /containers/instances/{id}/health` - Container health status
- `GET /test/integration` - Complete system validation

### **Service Discovery**
- `POST /registry/endpoints` - Register service endpoint
- `PUT /registry/endpoints/{id}/status` - Update endpoint status
- `DELETE /registry/endpoints/{id}` - Remove endpoint

## 🧪 Testing

### **Comprehensive Testing**
```bash
python test_system.py
```

### **Individual Endpoint Testing**
```bash
# Health check
curl http://localhost:8000/health

# System resources
curl http://localhost:8000/system/resources

# List containers
curl http://localhost:8000/containers

# Integration test
curl http://localhost:8000/test/integration
```

### **Container Lifecycle Testing**
```bash
# Start a test container
curl -X POST http://localhost:8000/containers/nginx:alpine/start \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "resources": {"cpu_limit": "0.1", "memory_limit": "128m"}}'
```

## 📊 Monitoring & Health

### **Health Status Levels**
- **🟢 Healthy** - CPU < 75%, Memory < 75%
- **🟡 Warning** - CPU 75-90%, Memory 75-90%
- **🔴 Critical** - CPU > 90%, Memory > 90%
- **⚫ Stopped** - Container not running

### **Metrics Collected**
- **CPU Usage** - Percentage of allocated CPU
- **Memory Usage** - Percentage of allocated memory
- **Disk Usage** - System disk utilization
- **Container Status** - Running/stopped state
- **Network Ports** - Host port mappings

## 🔄 Data Flow

### **1. Container Creation**
```
UI Request → FastAPI → Container Manager → Docker → Health Monitor → Database
```

### **2. Health Monitoring**
```
Health Monitor → Container Stats → Health Classification → Database → API Response
```

### **3. Service Discovery**
```
Container Start → Registry Update → Service Discovery → Load Balancer
```

## 🚨 Troubleshooting

### **Common Issues**

#### **Service Won't Start**
```bash
# Check logs
docker-compose logs -f api

# Check health
curl http://localhost:8000/health/detailed
```

#### **Container Creation Fails**
```bash
# Check Docker
docker ps
docker system df

# Check system resources
curl http://localhost:8000/system/resources
```

#### **Database Connection Issues**
```bash
# Check PostgreSQL
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### **Debug Commands**
```bash
# View all containers
docker ps --filter "label=managed-by"

# Check system logs
docker-compose logs -f

# Restart service
docker-compose restart api
```

## 📈 Performance & Scaling

### **Resource Limits**
- **CPU**: Fractional cores (e.g., "0.25" = 25% of one core)
- **Memory**: Standard Docker format (e.g., "512m", "1g")
- **Disk**: Currently not enforced (Docker limitation)

### **Scaling Capabilities**
- **Horizontal**: Multiple containers per image
- **Vertical**: Resource limit adjustments
- **Auto-scaling**: Based on health and resource usage

## 🔐 Security & Access

### **Current Implementation**
- **Docker socket access** for container management
- **PostgreSQL authentication** via environment variables
- **CORS enabled** for web UI integration

### **Production Considerations**
- **API authentication** (to be implemented)
- **Docker socket security** (consider Docker-in-Docker)
- **Network isolation** (consider custom Docker networks)

## 📚 Documentation Files

- **[README_APP.md](README_APP.md)** - Detailed `app.py` function documentation
- **[README_CONTAINER_SYSTEM.md](README_CONTAINER_SYSTEM.md)** - Container management system
- **[README_API.md](README_API.md)** - API specification and contracts

## 🎯 Ready for Integration

**Your system is production-ready for tomorrow's testing:**

✅ **All endpoints working** and tested  
✅ **Health monitoring active** and collecting data  
✅ **Container management** fully functional  
✅ **Database integration** working smoothly  
✅ **Error handling** robust and professional  
✅ **Comprehensive testing** completed  

## 🤝 Team Integration

### **For Team 1 (UI & API)**
- Connect to port 8000
- Use `/containers` and `/images` endpoints
- Monitor system health via `/health/detailed`

### **For Team 2 (Load Balancer)**
- Get container health via `/containers/instances/{id}/health`
- Discover services via registry endpoints
- Monitor system resources via `/system/resources`

### **For Team 4 (Billing)**
- Collect usage data via health endpoints
- Monitor container counts and resource usage
- Access historical data via database

### **For Team 5 (DevOps)**
- Run integration tests via `/test/integration`
- Monitor system health and performance
- Validate all component interactions

---

**🎉 Congratulations! You've built a professional-grade container orchestration system!**





