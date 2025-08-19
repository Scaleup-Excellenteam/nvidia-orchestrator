"""
Logging configuration for NVIDIA Orchestrator.

This module provides centralized logging configuration for the entire
application.
"""

from __future__ import annotations

import logging
import sys
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
    Configure a logger instance with console handler only.
    
    Args:
        logger_instance: Logger instance to configure.
    """
    logger_instance.setLevel(logging.INFO)

    # Format for log messages
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
    )

    # Console handler only - no file logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger_instance.addHandler(console_handler)


# Create a default logger instance for backward compatibility
logger = get_logger("nvidia-orchestrator")


# Export for convenience
__all__ = ["get_logger", "logger", "configure_logger"]
