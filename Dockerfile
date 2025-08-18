# Use a stable base that has manylinux wheels available for deps
FROM python:3.11-slim

# Avoid bytecode & ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

WORKDIR /app

# Install Python deps first to leverage cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY app.py container_manager.py postgres_store.py mongodb.py health_monitor.py /app/

EXPOSE 8000

# Default entrypoint is the API; compose will override for health-monitor
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
