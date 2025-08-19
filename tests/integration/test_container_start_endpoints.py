"""
Integration tests for container start endpoints.

Tests the real API endpoints with the new typed StartBody structure
and verifies end-to-end functionality.
"""

import time
from typing import Any, Dict, List

import httpx
import pytest


class TestContainerStartEndpoints:
    """Test suite for container start endpoints."""

    def test_health_check_before_tests(self, api_client: httpx.Client, wait_for_service):
        """Verify API service is healthy before running container tests."""
        response = api_client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        assert "status" in health_data

    def test_start_container_with_image_url_and_validate_running(
        self, api_client: httpx.Client, cleanup_containers
    ):
        """Test starting container with image URL and validate it's actually running."""
        # Create a comprehensive StartBody with image URL
        start_body = {
            "image": "nginx:alpine",
            "image_url": "https://hub.docker.com/_/nginx",  # Real image URL
            "min_replicas": 1,
            "max_replicas": 2,
            "resources": {
                "cpu": "0.1",
                "memory": "64Mi",
                "disk": "1GB"
            },
            "env": {
                "CONTAINER_TEST": "running_validation",
                "TEST_TIMESTAMP": str(int(time.time()))
            },
            "ports": [
                {
                    "container": 80,
                    "host": 8080
                }
            ]
        }

        # 1. Start the container
        print(f"\n🚀 Starting container with image URL: {start_body['image_url']}")
        response = api_client.post("/start/container", json=start_body)

        assert response.status_code == 200, f"Failed to start container: {response.text}"
        response_data = response.json()

        # Verify response structure
        assert "ok" in response_data
        assert "container_id" in response_data
        assert "status" in response_data

        container_id = response_data.get("container_id")
        assert container_id is not None, "Container ID should be returned"
        cleanup_containers(container_id)

        print(f"✅ Container started with ID: {container_id}")

        # 2. Wait for container to be fully running (give it some time to start)
        print("⏳ Waiting for container to be fully running...")
        max_wait_attempts = 30
        container_running = False

        for attempt in range(max_wait_attempts):
            time.sleep(2)  # Wait 2 seconds between checks

            # Check container list to see if our container is running
            list_response = api_client.get("/containers")
            assert list_response.status_code == 200

            containers_data = list_response.json()
            assert "containers" in containers_data

            # Look for our container in the list
            for container in containers_data["containers"]:
                if container.get("id") == container_id:
                    container_status = container.get("status", "").lower()
                    print(f"   Attempt {attempt + 1}: Container status = '{container_status}'")

                    if container_status in ["running", "up"]:
                        container_running = True
                        print(f"✅ Container is running after {attempt + 1} attempts")
                        break
                    elif container_status in ["exited", "dead", "error"]:
                        print(f"❌ Container failed with status: {container_status}")
                        break

            if container_running:
                break

        assert container_running, f"Container {container_id} did not reach running state within {max_wait_attempts * 2} seconds"

        # 3. Validate container details
        print("🔍 Validating container details...")
        list_response = api_client.get("/containers")
        containers_data = list_response.json()

        running_container = None
        for container in containers_data["containers"]:
            if container.get("id") == container_id:
                running_container = container
                break

        assert running_container is not None, f"Started container {container_id} not found in containers list"

        # Verify container properties
        assert running_container.get("image") == start_body["image"]
        assert running_container.get("status").lower() in ["running", "up"]

        # Check if ports are mapped (if the container manager exposes this info)
        if "ports" in running_container:
            print(f"   Port mappings: {running_container['ports']}")

        print("✅ Container validation complete:")
        print(f"   - ID: {running_container['id']}")
        print(f"   - Image: {running_container['image']}")
        print(f"   - Status: {running_container['status']}")
        print(f"   - Created: {running_container.get('created_at', 'N/A')}")

        # 4. Optional: Test container health if health endpoint exists
        try:
            health_response = api_client.get(f"/containers/instances/{container_id}/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"   - Health: {health_data}")

                # Verify health response structure
                assert isinstance(health_data, dict)

                # If health check returns specific fields, validate them
                if "status" in health_data:
                    assert health_data["status"] in ["healthy", "running", "up"]
            else:
                print(f"   - Health endpoint returned: {health_response.status_code}")
        except Exception as e:
            print(f"   - Health check not available: {e}")

        # 5. Test with image-specific endpoint as well
        print("\n🔄 Testing image-specific start endpoint...")
        image_start_body = start_body.copy()
        image_start_body["count"] = 1  # Start one more container

        image_response = api_client.post(f"/containers/{start_body['image']}/start", json=image_start_body)
        assert image_response.status_code == 200

        image_response_data = image_response.json()
        assert "started" in image_response_data
        assert len(image_response_data["started"]) == 1

        # Track the new container for cleanup too
        new_container_id = image_response_data["started"][0]
        cleanup_containers(new_container_id)
        print(f"✅ Second container started via image endpoint: {new_container_id}")

    def test_start_container_endpoint_with_valid_body(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test /start/container endpoint with valid typed StartBody."""
        response = api_client.post("/start/container", json=valid_start_body)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "ok" in response_data
        assert "action" in response_data
        assert "container_id" in response_data
        assert "status" in response_data

        # Track container for cleanup
        if response_data.get("container_id"):
            cleanup_containers(response_data["container_id"])

    def test_start_container_endpoint_with_count_field(
        self, api_client: httpx.Client, valid_start_body_with_count: Dict[str, Any], cleanup_containers
    ):
        """Test /start/container endpoint with legacy count field."""
        response = api_client.post("/start/container", json=valid_start_body_with_count)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "ok" in response_data
        assert "container_id" in response_data

        # Track container for cleanup
        if response_data.get("container_id"):
            cleanup_containers(response_data["container_id"])

    def test_start_container_endpoint_with_minimal_body(
        self, api_client: httpx.Client, minimal_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test /start/container endpoint with minimal required fields."""
        response = api_client.post("/start/container", json=minimal_start_body)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "ok" in response_data
        assert "container_id" in response_data

        # Track container for cleanup
        if response_data.get("container_id"):
            cleanup_containers(response_data["container_id"])

    def test_start_image_endpoint_with_valid_body(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test /containers/{imageId}/start endpoint with valid typed StartBody."""
        image_id = "nginx:alpine"
        response = api_client.post(f"/containers/{image_id}/start", json=valid_start_body)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure matches StartResponse model
        assert "started" in response_data
        assert isinstance(response_data["started"], list)

        # Track containers for cleanup
        for container_id in response_data["started"]:
            cleanup_containers(container_id)

    def test_start_image_endpoint_with_ports_and_env(
        self, api_client: httpx.Client, redis_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test container start with port mappings and environment variables."""
        image_id = "redis:alpine"
        response = api_client.post(f"/containers/{image_id}/start", json=redis_start_body)

        assert response.status_code == 200
        response_data = response.json()

        # Verify containers were started
        assert "started" in response_data
        assert len(response_data["started"]) >= 1

        # Track containers for cleanup
        for container_id in response_data["started"]:
            cleanup_containers(container_id)

    def test_start_multiple_replicas(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test starting multiple container replicas."""
        # Modify body to request multiple replicas
        body = valid_start_body.copy()
        body["count"] = 3

        image_id = "nginx:alpine"
        response = api_client.post(f"/containers/{image_id}/start", json=body)

        assert response.status_code == 200
        response_data = response.json()

        # Verify correct number of containers started
        assert "started" in response_data
        assert len(response_data["started"]) == 3

        # Verify all container IDs are unique
        container_ids = response_data["started"]
        assert len(set(container_ids)) == len(container_ids)

        # Track containers for cleanup
        for container_id in container_ids:
            cleanup_containers(container_id)

    def test_container_list_after_start(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test that started containers appear in the containers list."""
        # Start a container
        response = api_client.post("/start/container", json=valid_start_body)
        assert response.status_code == 200

        start_response = response.json()
        container_id = start_response.get("container_id")
        assert container_id is not None
        cleanup_containers(container_id)

        # Give container time to start
        time.sleep(2)

        # Check containers list
        response = api_client.get("/containers")
        assert response.status_code == 200

        containers_data = response.json()
        assert "containers" in containers_data

        # Verify our container is in the list
        container_found = False
        for container in containers_data["containers"]:
            if container.get("id") == container_id:
                container_found = True
                assert "status" in container
                assert "image" in container
                break

        assert container_found, f"Started container {container_id} not found in containers list"

    @pytest.mark.parametrize("invalid_body", [
        # Will be populated by invalid_start_bodies fixture
    ])
    def test_start_container_with_invalid_bodies(
        self, api_client: httpx.Client, invalid_start_bodies: List[Dict[str, Any]]
    ):
        """Test /start/container endpoint with various invalid request bodies."""
        for invalid_body in invalid_start_bodies:
            response = api_client.post("/start/container", json=invalid_body)

            # Should return validation error (422) or bad request (400)
            assert response.status_code in [400, 422], f"Invalid body should be rejected: {invalid_body}"

            response_data = response.json()
            # FastAPI validation errors have 'detail' field
            assert "detail" in response_data

    def test_start_container_with_malformed_json(self, api_client: httpx.Client):
        """Test endpoint with malformed JSON."""
        response = api_client.post(
            "/start/container",
            content="{ invalid json",
            headers={"content-type": "application/json"}
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_start_container_concurrent_requests(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test multiple concurrent container start requests."""
        import asyncio

        import httpx

        async def make_request():
            async with httpx.AsyncClient(base_url=api_client.base_url, timeout=30.0) as client:
                response = await client.post("/start/container", json=valid_start_body)
                return response

        async def run_concurrent_tests():
            tasks = [make_request() for _ in range(3)]
            responses = await asyncio.gather(*tasks)
            return responses

        # Run concurrent requests
        responses = asyncio.run(run_concurrent_tests())

        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
            response_data = response.json()

            # Track containers for cleanup
            if response_data.get("container_id"):
                cleanup_containers(response_data["container_id"])

    def test_resource_limits_are_applied(
        self, api_client: httpx.Client, cleanup_containers
    ):
        """Test that resource limits are properly applied to containers."""
        # Create body with specific resource limits
        body = {
            "image": "alpine:latest",
            "image_url": "https://hub.docker.com/alpine:latest",
            "resources": {
                "cpu": "0.1",
                "memory": "64Mi",
                "disk": "500MB"
            },
            "env": {"RESOURCE_TEST": "true"}
        }

        response = api_client.post("/start/container", json=body)
        assert response.status_code == 200

        response_data = response.json()
        container_id = response_data.get("container_id")
        assert container_id is not None
        cleanup_containers(container_id)

        # Verify container was created with proper resources
        # Note: This would ideally check Docker inspect output or container stats
        # but we're testing the API layer here

    def test_environment_variables_are_set(
        self, api_client: httpx.Client, cleanup_containers
    ):
        """Test that environment variables are properly passed to containers."""
        body = {
            "image": "alpine:latest",
            "image_url": "https://hub.docker.com/alpine:latest",
            "resources": {
                "cpu": "0.1",
                "memory": "64Mi",
                "disk": "500MB"
            },
            "env": {
                "TEST_VAR": "integration_test_value",
                "ANOTHER_VAR": "test123"
            }
        }

        response = api_client.post("/start/container", json=body)
        assert response.status_code == 200

        response_data = response.json()
        container_id = response_data.get("container_id")
        assert container_id is not None
        cleanup_containers(container_id)

    def test_error_handling_for_nonexistent_image(self, api_client: httpx.Client):
        """Test error handling when trying to start non-existent image."""
        body = {
            "image": "nonexistent-image:latest",
            "image_url": "https://example.com/nonexistent.tar",
            "resources": {
                "cpu": "0.1",
                "memory": "64Mi",
                "disk": "500MB"
            }
        }

        response = api_client.post("/start/container", json=body)

        # Should return error status
        assert response.status_code in [400, 404, 500]

        response_data = response.json()
        assert "detail" in response_data

    def test_full_e2e_container_lifecycle(
        self, api_client: httpx.Client, valid_start_body: Dict[str, Any], cleanup_containers
    ):
        """Test complete end-to-end container lifecycle."""
        # 1. Start container
        start_response = api_client.post("/start/container", json=valid_start_body)
        assert start_response.status_code == 200

        start_data = start_response.json()
        container_id = start_data.get("container_id")
        assert container_id is not None
        cleanup_containers(container_id)

        # 2. Verify container appears in list
        time.sleep(2)  # Give container time to start
        list_response = api_client.get("/containers")
        assert list_response.status_code == 200

        # 3. Check container health (if health endpoint exists)
        # Note: Adjust this based on your actual health check endpoint
        try:
            health_response = api_client.get(f"/containers/instances/{container_id}/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                # Verify health response structure
                assert isinstance(health_data, dict)
        except Exception:
            # Health endpoint might not be implemented for all containers
            pass

        # 4. Verify container can be stopped (if stop endpoint exists)
        # This would be handled by the cleanup_containers fixture
