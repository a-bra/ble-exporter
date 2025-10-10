# ABOUTME: File-only logging setup for BLE exporter application
# ABOUTME: Configures RotatingFileHandler with structured log format
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ble_exporter.config import AppConfig


def get_logger(app_config: AppConfig) -> logging.Logger:
    """
    Create and configure logger for the BLE exporter application.

    Args:
        app_config: Application configuration containing log file path

    Returns:
        Configured logger instance with file handler
    """
    logger = logging.getLogger('ble_exporter')

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Ensure log directory exists
    log_path = Path(app_config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler (10MB max, keep 5 backups)
    handler = RotatingFileHandler(
        app_config.log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )

    # Use structured format
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger
