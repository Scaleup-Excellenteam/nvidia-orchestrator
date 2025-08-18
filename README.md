# Nvidia-team3
# nvidia-orchestrator
src/
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── containers.py
│   │   ├── images.py
│   │   └── health.py
│   └── models/
│       ├── requests.py
│       └── responses.py
├── services/
│   ├── __init__.py
│   ├── container_service.py
│   ├── scaling_service.py
│   └── health_service.py
├── core/
│   ├── __init__.py
│   ├── container_manager.py
│   ├── config.py
│   └── events.py
└── utils/
    ├── __init__.py
    ├── docker_utils.py
    └── metrics.py




FROM python:3.12-slim

# התקנת dependencies
RUN apt-get update && apt-get install -y \
docker.io \
&& rm -rf /var/lib/apt/lists/*

# הגדרת תיקיית עבודה
WORKDIR /app

# העתקת requirements
COPY requirements.txt .

# התקנת Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קוד
COPY . .

# חשיפת פורט
EXPOSE 8000

# הרצה
CMD ["python", "-m", "uvicorn", "fast_api:app", "--host", "0.0.0.0", "--port", "8000"]





compose:
version: '3.8'
services:
  orchestrator:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DOCKER_HOST=unix:///var/run/docker.sock
    depends_on:
      - redis  # אם נוסיף caching

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"