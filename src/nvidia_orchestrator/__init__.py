"""
NVIDIA Orchestrator - Container orchestration system with health monitoring.

This package provides a complete container orchestration solution with:
- Docker container management
- Health monitoring and metrics collection
- PostgreSQL-based event and state storage
- RESTful API for container operations
- Service discovery and registry
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Team 3"
__email__ = "team3@example.com"

# Core exports
from nvidia_orchestrator.core.container_manager import ContainerManager
from nvidia_orchestrator.storage.postgres_store import PostgresStore
from nvidia_orchestrator.utils.logger import get_logger

__all__ = [
    "ContainerManager",
    "PostgresStore",
    "get_logger",
    "__version__",
]
