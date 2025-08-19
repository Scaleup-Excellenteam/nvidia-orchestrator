# NVIDIA Orchestrator Docker Image

## 🐳 Docker Image URL

```
ghcr.io/waeel87/nvidia-orchestrator:latest
```

## 📦 Image Details

- **Registry:** GitHub Container Registry (ghcr.io)
- **Image Size:** ~75 MB
- **Architecture:** amd64
- **Base Image:** python:3.11-slim-bookworm
- **Exposed Port:** 8000

## 🚀 Quick Usage

### Pull the Image
```bash
docker pull ghcr.io/waeel87/nvidia-orchestrator:latest
```

### Run the Container
```bash
# Basic run
docker run -p 8000:8000 ghcr.io/waeel87/nvidia-orchestrator:latest

# Run with environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  ghcr.io/waeel87/nvidia-orchestrator:latest

# Run with volume mounts
docker run -p 8000:8000 \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/waeel87/nvidia-orchestrator:latest
```

### Docker Compose
```yaml
version: '3.8'
services:
  nvidia-orchestrator:
    image: ghcr.io/waeel87/nvidia-orchestrator:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/orchestrator
    volumes:
      - ./logs:/app/logs
    depends_on:
      - db
      
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=orchestrator
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🔗 Links

- **Package Registry:** https://github.com/waeel87?tab=packages
- **Container Details:** https://github.com/users/waeel87/packages/container/package/nvidia-orchestrator
- **Health Check:** http://localhost:8000/health (after running)

## 📋 Available Tags

- `latest` - Latest stable build from main branch
- Tagged versions will be available as releases are created

---

*Last updated: December 2024* 