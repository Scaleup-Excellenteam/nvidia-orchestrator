#!/usr/bin/env python3
"""
Integration test runner for NVIDIA Orchestrator.

This script sets up the environment and runs integration tests
to verify the container start endpoints work correctly with the
new typed StartBody structure.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import requests


def wait_for_service(base_url: str = "http://localhost:8000", max_attempts: int = 30):
    """Wait for the API service to be ready."""
    print(f"⏳ Waiting for service at {base_url} to be ready...")

    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Service is ready after {attempt + 1} attempts")
                return True
        except Exception:
            pass

        if attempt < max_attempts - 1:
            time.sleep(1)

    print(f"❌ Service failed to start after {max_attempts} attempts")
    return False

def run_tests():
    """Run the integration tests."""
    # Set up environment
    os.environ["TEST_BASE_URL"] = "http://localhost:8000"

    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)

    print("🧪 Starting NVIDIA Orchestrator Integration Tests")
    print("=" * 60)

    # Wait for service to be ready
    if not wait_for_service():
        print("❌ Cannot run tests - service not available")
        return False

    # Run pytest with integration tests
    test_args = [
        sys.executable, "-m", "pytest",
        "tests/integration/test_container_start_endpoints.py",
        "-v",  # verbose output
        "-s",  # don't capture print statements
        "--tb=short",  # shorter traceback format
        "-x",  # stop on first failure
        "--color=yes"
    ]

    print(f"🔍 Running command: {' '.join(test_args)}")
    print("-" * 60)

    try:
        result = subprocess.run(test_args, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_quick_smoke_test():
    """Run a quick smoke test to verify basic functionality."""
    print("\n🚀 Running Quick Smoke Test")
    print("-" * 30)

    base_url = "http://localhost:8000"

    # Test 1: Health check
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check: PASS")
        else:
            print(f"❌ Health check: FAIL (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Health check: ERROR - {e}")
        return False

    # Test 2: Test new StartBody structure
    test_body = {
        "image": "hello-world:latest",
        "image_url": "https://hub.docker.com/hello-world:latest",
        "min_replicas": 1,
        "max_replicas": 1,
        "resources": {
            "cpu": "0.05",
            "memory": "32Mi",
            "disk": "500MB"
        },
        "env": {"TEST": "smoke_test"}
    }

    try:
        response = requests.post(
            f"{base_url}/start/container",
            json=test_body,
            timeout=30
        )
        if response.status_code == 200:
            print("✅ Container start with typed body: PASS")
            response_data = response.json()
            if "container_id" in response_data:
                print(f"   Container ID: {response_data['container_id']}")
        else:
            print(f"❌ Container start: FAIL (status: {response.status_code})")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Container start: ERROR - {e}")
        return False

    return True

def main():
    """Main function to run integration tests."""
    print("🐳 NVIDIA Orchestrator Integration Test Runner")
    print("=" * 50)

    # Check if pytest is available
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--version"],
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1

    # Run smoke test first
    if not run_quick_smoke_test():
        print("\n❌ Smoke test failed - aborting full test suite")
        return 1

    print("\n✅ Smoke test passed - running full integration tests")

    # Run full test suite
    if run_tests():
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print("\n❌ Some integration tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
