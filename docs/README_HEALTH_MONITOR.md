# Health Monitor - Real-Time Container Event Monitoring

## 🎯 Overview

The Health Monitor is a real-time event monitoring system that tracks container lifecycle changes and automatically notifies external services (Discovery Service and Billing Service) when containers are created, started, stopped, or removed.

## 🏗️ Architecture

### **Core Components**

#### **1. Container State Tracker**
- **Purpose**: Maintains in-memory state tracking for all managed containers
- **Functionality**: 
  - Tracks current state of each container
  - Detects state changes in real-time
  - Cleans up deleted containers automatically
- **Implementation**: Singleton pattern for global access

#### **2. Real-Time Event Detection**
- **Purpose**: Monitors containers every 60 seconds for state changes
- **Functionality**:
  - Compares current state with previous state
  - Triggers notifications only when changes occur
  - Handles all container lifecycle events

#### **3. Service Integration**
- **Discovery Service**: Automatic container registration and status updates
- **Billing Service**: Event logging for all container lifecycle changes

## 🔧 Features

### **State Change Detection**
- ✅ **Container Created** → `None` → `created`
- ✅ **Container Started** → `created` → `running`
- ✅ **Container Stopped** → `running` → `exited`
- ✅ **Container Removed** → `exited` → `removed`

### **Automatic Notifications**
- 📡 **Discovery Service**: Container registration, status updates, removal
- 💰 **Billing Service**: Event logging for billing and analytics
- 🔄 **Real-time**: Immediate notification upon state change detection

### **Error Handling**
- 🛡️ **Graceful Degradation**: Continues operation even if external services are unavailable
- 📝 **Comprehensive Logging**: Detailed logs for debugging and monitoring
- 🔁 **Retry Logic**: Built-in timeout handling for external service calls

## 📊 Data Flow

```
1. Health Monitor runs every 60 seconds
   ↓
2. Scans all managed containers
   ↓
3. Compares current state with previous state
   ↓
4. If state changed:
   ├── Send update to Discovery Service
   ├── Send event to Billing Service
   └── Update internal state tracking
   ↓
5. Continue with health monitoring
   ↓
6. Wait for next cycle
```

## 🚀 API Integration

### **Discovery Service Endpoints**

#### **Container Started**
```http
POST /registry/endpoints
{
  "id": "container_id",
  "image_id": "nginx:alpine",
  "host": "hostname",
  "port": 8000,
  "caps": {
    "cpu": "0.5",
    "mem": "256m"
  }
}
```

#### **Container Stopped**
```http
PUT /registry/endpoints/{container_id}/status?status=DOWN
```

#### **Container Removed**
```http
DELETE /registry/endpoints/{container_id}
```

### **Billing Service Events**

#### **Event Payload**
```json
{
  "event": "started|stopped|removed",
  "container_id": "container_id",
  "image": "nginx:alpine",
  "timestamp": "2025-08-19T07:17:22.193+00:00",
  "host": "hostname"
}
```

## ⚙️ Configuration

### **Environment Variables**
```bash
# Discovery Service
DISCOVERY_SERVICE_URL=http://localhost:7000

# Billing Service  
BILLING_SERVICE_URL=http://localhost:8001

# Health Monitor Settings
HEALTH_INTERVAL_SECONDS=60
HEALTH_RETENTION_DAYS=7
```

### **Docker Compose Integration**
```yaml
services:
  api:
    environment:
      DISCOVERY_SERVICE_URL: "http://localhost:7000"
      BILLING_SERVICE_URL: "http://localhost:8001"
      HEALTH_INTERVAL_SECONDS: "60"
      HEALTH_RETENTION_DAYS: "7"
```

## 🔍 Monitoring & Logging

### **Log Levels**
- **INFO**: State changes, service notifications, health collection
- **WARNING**: Failed service notifications, connection issues
- **ERROR**: Health monitoring failures, data collection errors
- **DEBUG**: Detailed container state tracking

### **Key Log Messages**
```
Container {id} state changed: {old_state} -> {new_state}
Discovery Service notified: {action} for {container_id}
Billing Service notified: {event_type} for {container_id}
Failed to notify Discovery Service: {error}
Failed to notify Billing Service: {error}
```

## 🧪 Testing

### **Manual Testing**
```bash
# 1. Start the system
docker-compose up -d

# 2. Create a test container
curl -X POST http://localhost:8000/start/container \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "resources": {"image": "nginx:alpine"}}'

# 3. Check logs for notifications
docker-compose logs -f api

# 4. Stop the container
curl -X DELETE http://localhost:8000/containers/{container_id}

# 5. Verify state change detection in logs
```

### **Expected Log Output**
```
Container {id} state changed: None -> running
Discovery Service notified: started for {container_id}
Billing Service notified: started for {container_id}

Container {id} state changed: running -> exited
Discovery Service notified: stopped for {container_id}
Billing Service notified: stopped for {container_id}
```

## 🚨 Troubleshooting

### **Common Issues**

#### **1. External Services Unavailable**
```
Failed to notify Discovery Service: Connection refused
Failed to notify Billing Service: Connection refused
```
**Solution**: Check if Discovery/Billing services are running on configured ports

#### **2. State Tracking Issues**
```
Container state not updating correctly
```
**Solution**: Check logs for state change detection, verify container labels

#### **3. Performance Issues**
```
Health monitoring taking too long
```
**Solution**: Adjust `HEALTH_INTERVAL_SECONDS`, check container count

### **Debug Commands**
```bash
# Check health monitor logs
docker-compose logs -f api | grep "state changed"

# Verify container states
curl http://localhost:8000/containers

# Check system health
curl http://localhost:8000/health/detailed
```

## 📈 Performance

### **Resource Usage**
- **Memory**: Minimal - only stores container IDs and states
- **CPU**: Low - simple state comparison every 60 seconds
- **Network**: Minimal - only when external services are called

### **Scalability**
- **Container Count**: Handles hundreds of containers efficiently
- **Update Frequency**: Configurable via `HEALTH_INTERVAL_SECONDS`
- **External Services**: Non-blocking calls with 5-second timeout

## 🔮 Future Enhancements

### **Planned Features**
- **Webhook Support**: Custom webhook endpoints for notifications
- **Event Filtering**: Configurable event types and conditions
- **Metrics Collection**: Performance and health metrics
- **Alert System**: Custom alerting for critical state changes

### **Integration Possibilities**
- **Prometheus**: Metrics export for monitoring
- **Grafana**: Dashboard integration
- **Slack/Discord**: Notification channels
- **Email**: Critical event notifications

## 📚 Related Documentation

- **[README.md](../README.md)** - Main project overview
- **[README_API.md](README_API.md)** - API documentation
- **[README_CONTAINER_SYSTEM.md](README_CONTAINER_SYSTEM.md)** - Container management system

## 🤝 Contributing

### **Code Standards**
- **Documentation**: All functions must have clear docstrings
- **Error Handling**: Comprehensive try-catch blocks
- **Logging**: Appropriate log levels for all operations
- **Testing**: Unit tests for all new functionality

### **Adding New Event Types**
1. Define the event in the state change detection logic
2. Add notification logic for Discovery Service
3. Add event logging for Billing Service
4. Update documentation and tests

---

**🎉 The Health Monitor provides real-time container lifecycle monitoring with automatic service integration, making it easy to track and respond to container state changes across your orchestration system.** 