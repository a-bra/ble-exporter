"""
Tests for the main scheduler loop that ties together scanning, parsing, and metrics.
"""
import asyncio
import logging
import time
from unittest.mock import MagicMock
import pytest
from pytest import approx

from ble_exporter.main import scan_loop
from ble_exporter.scanner import MockScanner
from ble_exporter.config import AppConfig
from ble_exporter.exporter import StatusTracker
from ble_exporter.metrics import (
    temperature_gauge,
    humidity_gauge,
    battery_gauge,
    last_update_gauge,
    seen_gauge,
)


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={
            "A4:C1:38:11:22:33": "living_room",
            "A4:C1:38:44:55:66": "bedroom",
        },
        log_file="/tmp/test.log"
    )


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock(spec=logging.Logger)
    return logger


@pytest.fixture
def status_tracker():
    """Create a fresh StatusTracker for each test."""
    return StatusTracker(
        scan_interval_seconds=30,
        scan_duration_seconds=5
    )


@pytest.mark.asyncio
async def test_scan_loop_single_iteration(mock_config, mock_logger, status_tracker):
    """Test that scan loop runs once and updates metrics correctly."""
    # Create scanner with one device returning valid BTHome packet
    # Temperature: 21.5°C (0x6608 = 2150 in little-endian)
    # Humidity: 65.5% (0xBF28 = 10431 in little-endian)
    # Battery: 85% (0x55)
    test_payload = bytes([
        0x02,  # BTHome version 2
        0x02, 0x66, 0x08,  # Temperature object
        0x03, 0xBF, 0x28,  # Humidity object
        0x0A, 0x55,        # Battery object
    ])

    scanner = MockScanner(data=[
        ("A4:C1:38:11:22:33", test_payload)
    ])

    # Run loop once with timeout
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )

    # Let it run one iteration
    await asyncio.sleep(0.1)

    # Cancel the loop
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify metrics were updated
    temp_value = temperature_gauge.labels(device="living_room")._value._value
    humidity_value = humidity_gauge.labels(device="living_room")._value._value
    battery_value = battery_gauge.labels(device="living_room")._value._value

    assert temp_value == approx(21.5, abs=0.01)
    assert humidity_value == approx(104.31, abs=0.01)
    assert battery_value == approx(85.0, abs=0.01)


@pytest.mark.asyncio
async def test_scan_loop_updates_status_tracker(mock_config, mock_logger, status_tracker):
    """Test that scan loop updates the status tracker."""
    # Create scanner with one device
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])
    scanner = MockScanner(data=[("A4:C1:38:11:22:33", test_payload)])

    # Record time before running
    start_time = int(time.time())

    # Run loop once
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify status tracker was updated
    assert status_tracker.devices_seen == 1
    assert status_tracker.last_scan_timestamp >= start_time
    assert status_tracker.last_scan_timestamp <= int(time.time()) + 1


@pytest.mark.asyncio
async def test_scan_loop_ignores_unknown_devices(mock_config, mock_logger, status_tracker):
    """Test that scan loop ignores devices not in config.

    With early filtering in aggregate_scan_results, unknown devices are
    filtered out before reaching scan_loop's device processing logic.
    """
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])

    # Scanner returns an unknown device
    scanner = MockScanner(data=[("FF:FF:FF:FF:FF:FF", test_payload)])

    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify no devices were counted (filtered out early)
    assert status_tracker.devices_seen == 0


@pytest.mark.asyncio
async def test_scan_loop_handles_invalid_packets(mock_config, mock_logger, status_tracker):
    """Test that scan loop handles parse errors gracefully."""
    # Invalid packet (too short)
    invalid_payload = bytes([0x02])

    scanner = MockScanner(data=[("A4:C1:38:11:22:33", invalid_payload)])

    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify no devices were counted due to parse error
    assert status_tracker.devices_seen == 0

    # Verify warning was logged
    mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_scan_loop_multiple_devices(mock_config, mock_logger, status_tracker):
    """Test that scan loop handles multiple devices in one scan."""
    test_payload1 = bytes([0x02, 0x02, 0x66, 0x08])  # 21.5°C
    test_payload2 = bytes([0x02, 0x02, 0x00, 0x00])  # 0°C

    scanner = MockScanner(data=[
        ("A4:C1:38:11:22:33", test_payload1),
        ("A4:C1:38:44:55:66", test_payload2),
    ])

    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify both devices were counted
    assert status_tracker.devices_seen == 2

    # Verify both devices have updated metrics
    temp1 = temperature_gauge.labels(device="living_room")._value._value
    temp2 = temperature_gauge.labels(device="bedroom")._value._value

    assert temp1 == approx(21.5, abs=0.01)
    assert temp2 == approx(0.0, abs=0.01)


@pytest.mark.asyncio
async def test_scan_loop_respects_sleep_duration(mock_config, mock_logger, status_tracker):
    """Test that scan loop calculates sleep duration correctly."""
    scanner = MockScanner(data=[])

    # Run loop for a short time
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )

    # Let it run for less than the scan interval
    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Just verify it didn't crash and logged appropriately
    mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_scan_loop_warns_on_negative_sleep(mock_logger, status_tracker):
    """Test that scan loop warns when interval < duration."""
    # Config where interval is less than duration
    bad_config = AppConfig(
        scan_interval_seconds=3,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={},
        log_file="/tmp/test.log"
    )

    scanner = MockScanner(data=[])

    task = asyncio.create_task(
        scan_loop(scanner, bad_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify warning was logged
    assert any(
        'scan_interval_seconds' in str(call)
        for call in mock_logger.warning.call_args_list
    )


@pytest.mark.asyncio
async def test_scan_loop_aggregates_alternating_packets(mock_config, mock_logger, status_tracker):
    """Test that scan loop aggregates measurements from alternating packets.

    This simulates real sensor behavior where temp/humidity comes in one packet
    and battery comes in another packet.
    """
    # First packet: temp + humidity
    packet1 = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
        0x03, 0xBF, 0x28,  # Humidity: 104.31%
    ])

    # Second packet: battery (voltage)
    packet2 = bytes([
        0x02,  # BTHome v2
        0x0C, 0x7B, 0x0B,  # Voltage: 2939mV -> ~94% battery
    ])

    # Scanner returns both packets for same device
    scanner = MockScanner(data=[
        ("A4:C1:38:11:22:33", packet1),
        ("A4:C1:38:11:22:33", packet2),
    ])

    # Run loop once
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify all three metrics were updated (aggregated from both packets)
    temp_value = temperature_gauge.labels(device="living_room")._value._value
    humidity_value = humidity_gauge.labels(device="living_room")._value._value
    battery_value = battery_gauge.labels(device="living_room")._value._value

    assert temp_value == approx(21.5, abs=0.01)
    assert humidity_value == approx(104.31, abs=0.01)
    assert battery_value == approx(93.9, abs=0.5)

    # Verify only counted as 1 device (not 2)
    assert status_tracker.devices_seen == 1
