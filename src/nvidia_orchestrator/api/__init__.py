"""
API module for NVIDIA Orchestrator.

This module provides the FastAPI-based REST API for container orchestration.
"""

from __future__ import annotations

__all__ = ["app", "run_server"]

def run_server() -> None:
    """Run the API server."""
    import uvicorn

    from nvidia_orchestrator.api.app import app

    uvicorn.run(app, host="0.0.0.0", port=8000)
