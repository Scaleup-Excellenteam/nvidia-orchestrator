#!/usr/bin/env python3
"""
Test script to start a container with image URL and validate it's actually running.

This script demonstrates the new typed StartBody structure and validates
that containers are properly started and running.
"""

import json
import sys
import time

import requests


def test_container_with_image_url():
    """Test starting container with image URL and validate it's running."""
    base_url = "http://localhost:8000"

    print("🐳 Testing Container Start with Image URL Validation")
    print("=" * 55)

    # 1. Check if API is ready
    try:
        health_response = requests.get(f"{base_url}/health", timeout=10)
        if health_response.status_code != 200:
            print("❌ API not ready - start the orchestrator first")
            return False
        print("✅ API is ready")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

    # 2. Create typed StartBody with image URL
    start_body = {
        "image": "httpd:alpine",
        "image_url": "https://hub.docker.com/_/httpd",
        "min_replicas": 1,
        "max_replicas": 2,
        "resources": {
            "cpu": "0.1",
            "memory": "64m",
            "disk": "1GB"
        },
        "env": {
            "CONTAINER_TEST": "image_url_validation",
            "TEST_TIMESTAMP": str(int(time.time()))
        },
        "ports": [
            {
                "container": 80,
                "host": 8082
            }
        ]
    }

    print(f"\n🚀 Starting container with image URL: {start_body['image_url']}")
    print(f"   Image: {start_body['image']}")
    print(f"   Resources: CPU={start_body['resources']['cpu']}, Memory={start_body['resources']['memory']}")
    print(f"   Port mapping: {start_body['ports'][0]['container']} -> {start_body['ports'][0]['host']}")

    # 3. Start the container
    try:
        start_response = requests.post(
            f"{base_url}/start/container",
            json=start_body,
            timeout=30
        )

        if start_response.status_code != 200:
            print(f"❌ Failed to start container: {start_response.status_code}")
            print(f"   Response: {start_response.text}")
            return False

        start_data = start_response.json()
        print("✅ Container start request successful")
        print(f"   Response: {json.dumps(start_data, indent=2)}")

        container_id = start_data.get("container_id")
        if not container_id:
            print("❌ No container ID returned")
            return False

        print(f"   Container ID: {container_id}")

    except Exception as e:
        print(f"❌ Error starting container: {e}")
        return False

    # 4. Wait and validate container is running
    print(f"\n⏳ Waiting for container {container_id} to be running...")
    max_attempts = 20
    container_running = False

    for attempt in range(max_attempts):
        try:
            time.sleep(3)  # Wait 3 seconds between checks

            # Get container list
            list_response = requests.get(f"{base_url}/containers", timeout=10)
            if list_response.status_code != 200:
                print(f"   Attempt {attempt + 1}: Failed to get container list")
                continue

            containers_data = list_response.json()
            if "containers" not in containers_data:
                print(f"   Attempt {attempt + 1}: Invalid container list response")
                continue

            # Find our container
            our_container = None
            for container in containers_data["containers"]:
                if container.get("id") == container_id:
                    our_container = container
                    break

            if not our_container:
                print(f"   Attempt {attempt + 1}: Container {container_id} not found in list")
                continue

            status = our_container.get("status", "unknown").lower()
            print(f"   Attempt {attempt + 1}: Container status = '{status}'")

            if status in ["running", "up"]:
                container_running = True
                print(f"✅ Container is running after {attempt + 1} attempts!")
                break
            elif status in ["exited", "dead", "error", "failed"]:
                print(f"❌ Container failed with status: {status}")
                break

        except Exception as e:
            print(f"   Attempt {attempt + 1}: Error checking status: {e}")

    if not container_running:
        print(f"❌ Container did not reach running state after {max_attempts} attempts")
        return False

    # 5. Get final container details
    print("\n🔍 Final container validation...")
    try:
        list_response = requests.get(f"{base_url}/containers", timeout=10)
        containers_data = list_response.json()

        running_container = None
        for container in containers_data["containers"]:
            if container.get("id") == container_id:
                running_container = container
                break

        if running_container:
            print("✅ Container Details:")
            print(f"   - ID: {running_container.get('id')}")
            print(f"   - Image: {running_container.get('image')}")
            print(f"   - Status: {running_container.get('status')}")
            print(f"   - Name: {running_container.get('name', 'N/A')}")

            if "ports" in running_container:
                print(f"   - Ports: {running_container['ports']}")

            if "created_at" in running_container:
                print(f"   - Created: {running_container['created_at']}")

            # Test if container is accessible on mapped port
            if start_body["ports"]:
                host_port = start_body["ports"][0]["host"]
                print(f"\n🌐 Testing container accessibility on port {host_port}...")
                try:
                    test_response = requests.get(f"http://localhost:{host_port}", timeout=5)
                    if test_response.status_code == 200:
                        print(f"✅ Container is accessible on port {host_port}")
                    else:
                        print(f"⚠️  Container responded with status {test_response.status_code}")
                except Exception as e:
                    print(f"⚠️  Container not accessible on port {host_port}: {e}")

    except Exception as e:
        print(f"⚠️  Error getting final details: {e}")

    # 6. Test health endpoint if available
    print("\n🔍 Testing container health endpoint...")
    try:
        health_response = requests.get(f"{base_url}/containers/instances/{container_id}/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print("✅ Container health check successful:")
            print(f"   Health data: {json.dumps(health_data, indent=2)}")
        else:
            print(f"⚠️  Health endpoint returned: {health_response.status_code}")
    except Exception as e:
        print(f"⚠️  Health check not available: {e}")

    print("\n🎉 Test completed successfully!")
    print(f"   Container {container_id} is running with image URL: {start_body['image_url']}")
    print(f"\n💡 To see all containers: curl {base_url}/containers")
    print(f"💡 To stop this container: curl -X POST {base_url}/containers/{start_body['image']}/stop")

    return True

def main():
    """Main function."""
    success = test_container_with_image_url()

    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
