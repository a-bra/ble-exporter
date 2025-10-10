# ABOUTME: Unit tests for logging module
# ABOUTME: Tests log file creation, message writing, and handler configuration
import logging
from pathlib import Path

from ble_exporter.config import AppConfig
from ble_exporter.logger import get_logger


def test_logger_creates_log_file(tmp_path):
    """Test that logger creates log file at specified path."""
    log_file = tmp_path / "logs" / "test.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger = get_logger(config)
    logger.info("Test message")

    assert log_file.exists()


def test_logger_writes_message(tmp_path):
    """Test that logger writes formatted messages to file."""
    log_file = tmp_path / "test.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger = get_logger(config)
    test_message = "Test log message"
    logger.info(test_message)

    # Force flush
    for handler in logger.handlers:
        handler.flush()

    log_content = log_file.read_text()
    assert test_message in log_content
    assert "INFO" in log_content


def test_logger_has_single_handler(tmp_path):
    """Test that logger attaches exactly one handler."""
    log_file = tmp_path / "test.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger = get_logger(config)

    assert len(logger.handlers) == 1


def test_logger_reuses_existing_handlers(tmp_path):
    """Test that calling get_logger multiple times doesn't add duplicate handlers."""
    log_file = tmp_path / "test.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger1 = get_logger(config)
    logger2 = get_logger(config)

    # Should be same instance
    assert logger1 is logger2
    # Should still only have one handler
    assert len(logger1.handlers) == 1


def test_logger_creates_parent_directories(tmp_path):
    """Test that logger creates parent directories if they don't exist."""
    log_file = tmp_path / "nested" / "path" / "to" / "log.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger = get_logger(config)
    logger.info("Test message")

    assert log_file.parent.exists()
    assert log_file.exists()


def test_logger_level_is_info(tmp_path):
    """Test that logger default level is INFO."""
    log_file = tmp_path / "test.log"

    config = AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file=str(log_file)
    )

    # Clear any existing handlers from previous tests
    logger = logging.getLogger('ble_exporter')
    logger.handlers.clear()

    logger = get_logger(config)

    assert logger.level == logging.INFO
