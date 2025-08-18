import os
import logging
"""
add this module into your project
"""

# constant of my service name - change per service
SERVICE_NAME = "nvidia-orchestrator"

# Get log file path from environment variable (default: /app/logs/combined.log)
log_dir = os.path.join(os.path.dirname(__file__), "app/logs")
log_file_path = os.path.join(log_dir, "combined.log")


# If using the default path, ensure the directory exists
os.makedirs(log_dir, exist_ok=True)
log_file = os.environ.get("LOG_FILE", log_file_path)


# Configure logging
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(message)s'
)

# set the logger name
logger = logging.getLogger(SERVICE_NAME)

# use case:
#   1. from logger import logger
#   2. logger.info("some log message")
#   3. logger.error("some error message")
