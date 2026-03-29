import os
import sys

from loguru import logger

# Remove default handler
logger.remove()

# Get log level from environment or default to INFO
LOG_LEVEL = os.environ.get("JANUS_LOG_LEVEL", "INFO")

# Add standard configurable handler
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
)

__all__ = ["logger"]
