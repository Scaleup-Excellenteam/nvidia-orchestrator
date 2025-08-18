# NVIDIA Orchestrator

A container orchestration system built with FastAPI, Docker, and PostgreSQL.

## 🚀 Current Status

**Version:** Middle Release  
**Status:** Core infrastructure complete, ready for testing  
**Components:** ✅ Database, ✅ Container Management, ✅ Logging, ✅ API Framework  

## 🏗️ What It Does

- **Container Management**: Start, stop, delete Docker containers
- **Health Monitoring**: Track container CPU, memory, and disk usage  
- **Event Logging**: Record all container lifecycle events
- **PostgreSQL Storage**: Persistent storage for events and health data

## 🚀 Quick Start

### Prerequisites
- Docker Desktop running
- Port 8000 available

### Run Everything
```bash
docker-compose up
```

This starts:
- PostgreSQL database
- Database initialization
- FastAPI server on port 8000

### Test Basic Health
```bash
curl http://localhost:8000/health
```

## 📁 Project Structure

```
├── app.py                 # FastAPI main application
├── container_manager.py   # Docker container operations
├── postgres_store.py      # Database operations
├── health_monitor.py      # Health monitoring service
├── logger.py             # Centralized logging
├── docker-compose.yml    # Service orchestration
├── db-init.sql          # Database schema
└── tests/               # Test suite
```

## 🔧 API Endpoints

- `POST /containers/{image}/start` - Start containers
- `GET /containers/{image}/instances` - List instances
- `GET /containers/instances/{id}/health` - Check health
- `POST /containers/{image}/stop` - Stop container
- `DELETE /containers/{image}` - Delete container
- `GET /events` - List events
- `GET /health` - API health check

## 📊 Logging

Logs are written to `app/logs/combined.log` by default.  
Set `LOG_FILE` environment variable to customize location.

## 🧪 Testing

```bash
# Run basic tests
python tests/test_simple.py

# Run integration tests (requires Docker)
pytest tests/
```

## 📋 Next Steps

- [ ] Fix API endpoint alignment with tests
- [ ] Integrate health monitor service
- [ ] Add comprehensive error handling
- [ ] Performance optimization

## 🤝 Contributing

This is a development version. Report issues and suggest improvements!





