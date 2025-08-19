"""
Logging configuration for NVIDIA Orchestrator.

This module provides centralized logging configuration for the entire application.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name. If None, uses the default service name.
        
    Returns:
        Configured logger instance.
    """
    if name is None:
        name = "nvidia-orchestrator"

    # Check if logger already exists
    logger_instance = logging.getLogger(name)

    # Only configure if not already configured
    if not logger_instance.handlers:
        configure_logger(logger_instance)

    return logger_instance


def configure_logger(logger_instance: logging.Logger) -> None:
    """
    Configure a logger instance with file and console handlers.
    
    Args:
        logger_instance: Logger instance to configure.
    """
    logger_instance.setLevel(logging.INFO)

    # Format for log messages
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
    )

    # Try to set up file logging
    log_file = os.environ.get("LOG_FILE")
    if not log_file:
        # Default log location
        log_dir = Path(__file__).parent.parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "combined.log"

    try:
        if isinstance(log_file, str):
            log_file = Path(log_file)

        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger_instance.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, just use console
        print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

    # Console handler (always add)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger_instance.addHandler(console_handler)


# Create a default logger instance for backward compatibility
logger = get_logger("nvidia-orchestrator")


# Export for convenience
__all__ = ["get_logger", "logger", "configure_logger"]
