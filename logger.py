import os
import logging
import sys
"""
add this module into your project
"""

# constant of my service name - change per service
SERVICE_NAME = "nvidia-orchestrator"

# Get log file path from environment variable (default: /app/logs/combined.log)
log_dir = os.path.join(os.path.dirname(__file__), "logs")
log_file_path = os.path.join(log_dir, "combined.log")

# If using the default path, ensure the directory exists
try:
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.environ.get("LOG_FILE", log_file_path)
except Exception:
    # If we can't create the log directory, just use console logging
    log_file = None

# Configure logging
if log_file and os.access(os.path.dirname(log_file), os.W_OK):
    # File logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(name)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)  # Also log to console
        ]
    )
else:
    # Console only logging (for container environments)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(name)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

# set the logger name
logger = logging.getLogger(SERVICE_NAME)

# use case:
#   1. from logger import logger
#   2. logger.info("some log message")
#   3. logger.error("some error message")
