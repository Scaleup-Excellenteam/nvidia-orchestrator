# Multi-stage Dockerfile for NVIDIA Orchestrator

# Base stage with common dependencies
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH=/app/src:${PYTHONPATH} \
    PYTHONUNBUFFERED=1 \
    LOG_FILE=/app/logs/combined.log

# Development stage
FROM base AS development

# Copy package files
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src/ ./src/

# Install the package in editable mode with dev dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev,test]"

# Create necessary directories
RUN mkdir -p /app/logs /app/scripts

# Copy scripts
COPY scripts/ ./scripts/
RUN chmod +x scripts/*.sh

# Development uses mounted volumes, so no need to copy source again
EXPOSE 8000

# Use regular python for development (allows reload)
CMD ["python", "-m", "nvidia_orchestrator.main"]

# Production stage
FROM base AS production

# Copy package files
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src/ ./src/

# Install the package (non-editable mode)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create necessary directories
RUN mkdir -p /app/logs /app/scripts

# Copy scripts
COPY scripts/ ./scripts/
RUN chmod +x scripts/*.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Use the entry point to run the server
ENTRYPOINT ["nvidia-orchestrator-server"]

# Default to production stage
FROM production
