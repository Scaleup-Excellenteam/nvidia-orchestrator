"""
API test fixtures for integration tests.
"""

import os
import time
from typing import Any, Dict, List

import httpx
import pytest


@pytest.fixture
def base_url() -> str:
    """Base URL for the API server."""
    return os.getenv("TEST_BASE_URL", "http://localhost:8000")


@pytest.fixture
def api_client(base_url: str) -> httpx.Client:
    """HTTP client for API requests."""
    return httpx.Client(base_url=base_url, timeout=30.0)


@pytest.fixture
def wait_for_service(api_client: httpx.Client, base_url: str) -> None:
    """Wait for the API service to be ready before running tests."""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = api_client.get("/health")
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)

    raise RuntimeError(f"Service at {base_url} did not become ready after {max_attempts} seconds")


@pytest.fixture
def valid_start_body() -> Dict[str, Any]:
    """Valid StartBody structure for testing."""
    return {
        "image": "nginx:alpine",
        "image_url": "https://hub.docker.com/nginx:alpine",
        "min_replicas": 1,
        "max_replicas": 3,
        "resources": {
            "cpu": "0.1",
            "memory": "64Mi",
            "disk": "1GB"
        },
        "env": {
            "TEST_ENV": "integration_test",
            "NODE_ENV": "test"
        },
        "ports": [
            {
                "container": 80,
                "host": 8080
            }
        ]
    }


@pytest.fixture
def valid_start_body_with_count(valid_start_body: Dict[str, Any]) -> Dict[str, Any]:
    """Valid StartBody with legacy count field."""
    body = valid_start_body.copy()
    body["count"] = 2
    return body


@pytest.fixture
def minimal_start_body() -> Dict[str, Any]:
    """Minimal valid StartBody structure."""
    return {
        "image": "hello-world:latest",
        "image_url": "https://hub.docker.com/hello-world:latest",
        "resources": {
            "cpu": "0.05",
            "memory": "32Mi",
            "disk": "500MB"
        }
    }


@pytest.fixture
def redis_start_body() -> Dict[str, Any]:
    """StartBody for Redis container with port mapping."""
    return {
        "image": "redis:alpine",
        "image_url": "https://hub.docker.com/redis:alpine",
        "min_replicas": 1,
        "max_replicas": 2,
        "resources": {
            "cpu": "0.1",
            "memory": "128Mi",
            "disk": "1GB"
        },
        "env": {},
        "ports": [
            {
                "container": 6379,
                "host": 6379
            }
        ]
    }


@pytest.fixture
def invalid_start_bodies() -> List[Dict[str, Any]]:
    """List of invalid StartBody structures for negative testing."""
    return [
        # Missing required image field
        {
            "image_url": "https://example.com/image.tar",
            "resources": {"cpu": "0.1", "memory": "64Mi", "disk": "1GB"}
        },
        # Missing required image_url field
        {
            "image": "nginx:alpine",
            "resources": {"cpu": "0.1", "memory": "64Mi", "disk": "1GB"}
        },
        # Missing required resources field
        {
            "image": "nginx:alpine",
            "image_url": "https://example.com/image.tar"
        },
        # Invalid resources structure
        {
            "image": "nginx:alpine",
            "image_url": "https://example.com/image.tar",
            "resources": "invalid"
        },
        # Invalid min_replicas (negative)
        {
            "image": "nginx:alpine",
            "image_url": "https://example.com/image.tar",
            "min_replicas": -1,
            "resources": {"cpu": "0.1", "memory": "64Mi", "disk": "1GB"}
        },
        # Invalid port mapping
        {
            "image": "nginx:alpine",
            "image_url": "https://example.com/image.tar",
            "resources": {"cpu": "0.1", "memory": "64Mi", "disk": "1GB"},
            "ports": [{"container": "invalid", "host": 8080}]
        }
    ]


@pytest.fixture
def cleanup_containers(api_client: httpx.Client):
    """Fixture to cleanup test containers after tests."""
    created_containers = []

    def add_container(container_id: str):
        created_containers.append(container_id)

    yield add_container

    # Cleanup after test
    for container_id in created_containers:
        try:
            # Stop and remove container
            api_client.post(f"/containers/{container_id}/stop")
            time.sleep(1)
            # Note: You might need to add a delete endpoint or use Docker API directly
        except Exception as e:
            print(f"Warning: Failed to cleanup container {container_id}: {e}")


@pytest.fixture
def sample_image_ids() -> List[str]:
    """Sample image IDs for testing."""
    return [
        "nginx:alpine",
        "redis:alpine",
        "hello-world:latest",
        "alpine:latest"
    ]
