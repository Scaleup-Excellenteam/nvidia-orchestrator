"""
Pytest configuration for NVIDIA Orchestrator tests.
"""

import os
import sys

import pytest

# Add the src directory to the Python path
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, os.path.abspath(src_path))

# Import test fixtures
from tests.fixtures.api_fixtures import *


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before running tests."""
    # Set test environment variables
    os.environ["TEST_MODE"] = "true"
    os.environ["LOG_LEVEL"] = "INFO"

    # You might want to start the API server here for integration tests
    # or configure it to use test database, etc.

    yield

    # Cleanup after all tests
    pass

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_docker: marks tests that require Docker to be running"
    )
