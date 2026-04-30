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
from ble_exporter.config import AppConfig, DeviceConfig
from ble_exporter.exporter import StatusTracker
from ble_exporter.metrics import (
    update_metrics,
    temperature_gauge,
    humidity_gauge,
    battery_gauge,
    last_update_gauge,
    seen_gauge,
)
from prometheus_client import REGISTRY


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={
            "A4:C1:38:11:22:33": DeviceConfig(name="living_room"),
            "A4:C1:38:44:55:66": DeviceConfig(name="bedroom"),
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
    # Humidity: 104.31% (0xBF28 = 10431 in little-endian)
    # Voltage: 2750mV (0xBE0A = 2750 in little-endian) -> 75% battery
    test_payload = bytes([
        0x02,  # BTHome version 2
        0x02, 0x66, 0x08,  # Temperature object
        0x03, 0xBF, 0x28,  # Humidity object
        0x0C, 0xBE, 0x0A,  # Voltage object (parser converts to battery %)
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
    assert battery_value == approx(75.0, abs=0.01)


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


@pytest.mark.asyncio
async def test_scan_loop_recovers_from_transient_scanner_error(mock_config, mock_logger, status_tracker):
    """Test that scan loop logs errors and continues after transient scanner failure."""
    # Create scanner that fails first call, then succeeds
    call_count = 0
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])  # Valid temp packet

    async def failing_scan(duration_s):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("BLE adapter not available")
        return [("A4:C1:38:11:22:33", test_payload)]

    scanner = MagicMock()
    scanner.scan = failing_scan

    # Run loop long enough for failure + 5s retry sleep + recovery
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(5.5)  # Let it fail once and retry
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify error was logged with full traceback
    mock_logger.error.assert_called()
    error_call = mock_logger.error.call_args
    assert "Error in scan loop" in str(error_call)
    assert error_call[1].get('exc_info') is True  # Verify exc_info=True was passed

    # Verify scan was attempted at least twice (retry happened)
    assert call_count >= 2


@pytest.mark.asyncio
async def test_scan_loop_continues_after_multiple_consecutive_failures(mock_config, mock_logger, status_tracker):
    """Test that scan loop keeps retrying after multiple consecutive scanner failures."""
    call_count = 0

    async def multi_failing_scan(duration_s):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise OSError(f"BLE scan failed (attempt {call_count})")
        # Succeed on 4th attempt
        return [("A4:C1:38:11:22:33", bytes([0x02, 0x02, 0x66, 0x08]))]

    scanner = MagicMock()
    scanner.scan = multi_failing_scan

    # Run loop long enough for 3 failures (each with 5s retry) + success
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(16)  # 3 failures * 5s + buffer
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify all 3 errors were logged
    assert mock_logger.error.call_count >= 3

    # Verify scanner was called at least 4 times (3 failures + 1 success)
    assert call_count >= 4


@pytest.mark.asyncio
async def test_scan_loop_updates_metrics_after_error_recovery(mock_config, mock_logger, status_tracker):
    """Test that metrics are correctly updated after scanner recovers from error."""
    call_count = 0
    test_payload = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
    ])

    async def failing_then_succeeding_scan(duration_s):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("BLE adapter error")
        return [("A4:C1:38:11:22:33", test_payload)]

    scanner = MagicMock()
    scanner.scan = failing_then_succeeding_scan

    # Run loop long enough for error recovery
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(5.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify metrics WERE updated after recovery
    temp_value = temperature_gauge.labels(device="living_room")._value._value
    assert temp_value == approx(21.5, abs=0.01)

    # Verify status tracker reflects successful scan
    assert status_tracker.devices_seen == 1
    assert status_tracker.last_scan_timestamp > 0


@pytest.mark.asyncio
async def test_scan_loop_does_not_update_status_tracker_on_error(mock_config, mock_logger, status_tracker):
    """Test that status tracker is NOT updated when scanner fails."""
    # Record initial state
    initial_timestamp = status_tracker.last_scan_timestamp
    initial_devices = status_tracker.devices_seen

    async def always_failing_scan(duration_s):
        raise RuntimeError("BLE adapter permanently unavailable")

    scanner = MagicMock()
    scanner.scan = always_failing_scan

    # Run loop briefly (will fail immediately + 5s sleep)
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.5)  # Just long enough to hit the error
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify status tracker was NOT updated (still at initial values)
    assert status_tracker.last_scan_timestamp == initial_timestamp
    assert status_tracker.devices_seen == initial_devices

    # Verify error was logged
    mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_scan_loop_handles_different_exception_types(mock_config, mock_logger, status_tracker):
    """Test that scan loop catches various exception types from scanner."""
    call_count = 0
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])

    async def various_errors_scan(duration_s):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Device I/O error")
        elif call_count == 2:
            raise ValueError("Invalid BLE parameter")
        elif call_count == 3:
            raise PermissionError("Insufficient permissions")
        return [("A4:C1:38:11:22:33", test_payload)]

    scanner = MagicMock()
    scanner.scan = various_errors_scan

    # Run loop long enough for all error types + recovery
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(16)  # 3 errors * 5s + buffer
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify all different exception types were caught and logged
    assert mock_logger.error.call_count >= 3

    # Verify scanner eventually succeeded
    assert call_count >= 4

    # Verify final state is healthy (metrics updated after recovery)
    assert status_tracker.devices_seen == 1


@pytest.mark.asyncio
async def test_scan_loop_clears_metrics_for_unseen_devices(mock_config, mock_logger, status_tracker):
    """Test that scan loop removes metrics for devices not seen in a scan.

    When a configured device is not detected during a scan, its sensor metrics
    (temperature, humidity, battery, last_update) should be removed from the
    registry, and its seen_gauge should be set to 0.
    """
    # Pre-populate metrics for both devices so we can verify clearing
    update_metrics("living_room", {'temperature': 20.0, 'humidity': 50.0, 'battery': 80.0})
    update_metrics("bedroom", {'temperature': 18.0, 'humidity': 45.0, 'battery': 70.0})

    # Scanner only returns living_room, bedroom is absent
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])  # Temperature: 21.5°C
    scanner = MockScanner(data=[("A4:C1:38:11:22:33", test_payload)])

    # Run one scan loop iteration
    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify living_room was updated (seen device)
    temp_lr = temperature_gauge.labels(device="living_room")._value._value
    assert temp_lr == approx(21.5, abs=0.01)
    assert seen_gauge.labels(device="living_room")._value._value == 1.0

    # Verify bedroom sensor metrics are REMOVED from registry
    bedroom_metrics = set()
    for metric_family in REGISTRY.collect():
        for sample in metric_family.samples:
            if sample.labels.get('device') == 'bedroom':
                bedroom_metrics.add(metric_family.name)

    assert 'ble_sensor_temperature_celsius' not in bedroom_metrics
    assert 'ble_sensor_humidity_percent' not in bedroom_metrics
    assert 'ble_sensor_battery_percent' not in bedroom_metrics
    assert 'ble_sensor_last_update_timestamp_seconds' not in bedroom_metrics

    # Verify bedroom seen_gauge is 0 (still present as presence indicator)
    assert seen_gauge.labels(device="bedroom")._value._value == 0.0


@pytest.mark.asyncio
async def test_scan_loop_updates_latest_readings(mock_config, mock_logger, status_tracker):
    """Test that scan loop populates the latest_readings dict after a scan.

    The readings dict should be updated with temperature, humidity, and a
    last_seen timestamp for each seen device. Unseen devices should keep
    their previous readings (or remain None).
    """
    test_payload = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
        0x03, 0xBF, 0x28,  # Humidity: 104.31%
        0x0C, 0xBE, 0x0A,  # Voltage: 2750mV -> 75% battery
    ])

    scanner = MockScanner(data=[("A4:C1:38:11:22:33", test_payload)])

    # Initialize readings dict with all devices as None (never seen)
    latest_readings = {"living_room": None, "bedroom": None}

    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger,
                  latest_readings=latest_readings)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # living_room was seen - should have readings
    assert latest_readings["living_room"] is not None
    assert latest_readings["living_room"]["temperature"] == approx(21.5, abs=0.01)
    assert latest_readings["living_room"]["humidity"] == approx(104.31, abs=0.01)
    assert "last_seen" in latest_readings["living_room"]

    # bedroom was not seen - should remain None
    assert latest_readings["bedroom"] is None


@pytest.mark.asyncio
async def test_scan_loop_battery_only_does_not_overwrite_readings(mock_config, mock_logger, status_tracker):
    """Test that a battery-only scan does not overwrite existing dashboard readings.

    When the scan window only captures a voltage/battery packet (no temp/humidity),
    the latest_readings dict should keep the previous values intact.
    """
    # Battery-only packet (voltage object, no temp or humidity)
    battery_payload = bytes([
        0x02,  # BTHome v2
        0x0C, 0xBE, 0x0A,  # Voltage: 2750mV -> 75% battery
    ])

    scanner = MockScanner(data=[("A4:C1:38:11:22:33", battery_payload)])

    # Pre-populate with previous good readings
    latest_readings = {
        "living_room": {
            "temperature": 21.5,
            "humidity": 65.0,
            "last_seen": "2026-03-28 14:00:00",
        },
        "bedroom": None,
    }

    task = asyncio.create_task(
        scan_loop(scanner, mock_config, status_tracker, mock_logger,
                  latest_readings=latest_readings)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # living_room was seen but only battery - readings should be unchanged
    assert latest_readings["living_room"]["temperature"] == approx(21.5, abs=0.01)
    assert latest_readings["living_room"]["humidity"] == approx(65.0, abs=0.01)
    assert latest_readings["living_room"]["last_seen"] == "2026-03-28 14:00:00"
