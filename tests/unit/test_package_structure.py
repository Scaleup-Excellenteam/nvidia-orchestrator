"""
Unit tests for validating package structure and imports.
"""

from pathlib import Path

import pytest


def test_package_imports():
    """Test that all main package modules can be imported."""
    # Test main package import
    import nvidia_orchestrator

    # Test version is defined
    assert hasattr(nvidia_orchestrator, '__version__')
    assert nvidia_orchestrator.__version__ == "1.0.0"

    # Test main exports
    assert hasattr(nvidia_orchestrator, 'ContainerManager')
    assert hasattr(nvidia_orchestrator, 'PostgresStore')
    assert hasattr(nvidia_orchestrator, 'get_logger')


def test_api_module():
    """Test API module imports."""
    from nvidia_orchestrator.api import run_server

    assert callable(run_server)


def test_core_module():
    """Test core module imports."""
    from nvidia_orchestrator.core import ContainerManager

    assert hasattr(ContainerManager, '__init__')


def test_storage_module():
    """Test storage module imports."""
    from nvidia_orchestrator.storage import PostgresStore

    assert hasattr(PostgresStore, '__init__')


def test_monitoring_module():
    """Test monitoring module imports."""
    from nvidia_orchestrator.monitoring import run_forever, sample_once

    assert callable(run_forever)
    assert callable(sample_once)


def test_utils_module():
    """Test utils module imports."""
    from nvidia_orchestrator.utils import get_logger, logger

    assert callable(get_logger)
    assert hasattr(logger, 'info')


def test_cli_module():
    """Test CLI module imports."""
    from nvidia_orchestrator.cli import main

    assert callable(main)


def test_project_structure():
    """Test that the project follows src-layout."""
    # Get the project root (parent of tests directory)
    project_root = Path(__file__).parent.parent.parent

    # Check src-layout structure
    assert (project_root / "src").exists()
    assert (project_root / "src" / "nvidia_orchestrator").exists()

    # Check other directories
    assert (project_root / "tests").exists()
    assert (project_root / "docs").exists()
    assert (project_root / "scripts").exists()

    # Check configuration files
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "README.md").exists()
    assert (project_root / "LICENSE").exists()
    assert (project_root / "Dockerfile").exists()
    assert (project_root / "docker-compose.yml").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
