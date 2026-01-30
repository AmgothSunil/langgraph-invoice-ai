"""
Configuration Package

Contains configuration utilities:
- logger: Logging setup with file rotation
- exception: Custom exception handling
"""

from src.config.logger import setup_logger
from src.config.exception import AppException, error_message_detail

__all__ = [
    "setup_logger",
    "AppException",
    "error_message_detail",
]
