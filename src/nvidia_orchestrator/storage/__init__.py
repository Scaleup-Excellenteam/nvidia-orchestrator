"""
Storage module for NVIDIA Orchestrator.

This module provides database storage capabilities using PostgreSQL.
"""

from __future__ import annotations

from nvidia_orchestrator.storage.postgres_store import PostgresStore

__all__ = ["PostgresStore"]
