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

# Copy source files
COPY app.py container_manager.py postgres_store.py health_monitor.py logger.py /app/
COPY start.sh /app/start.sh

# Create logs directory, normalize line endings, and make startup script executable
RUN mkdir -p /app/logs \
    && sed -i 's/\r$//' /app/start.sh \
    && chmod +x /app/start.sh

EXPOSE 8000

# Use the startup script
CMD ["/app/start.sh"]
