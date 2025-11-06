# ABOUTME: Tests for measurement aggregation logic
# ABOUTME: Tests grouping and merging of BLE packets by MAC address
import logging
from unittest.mock import MagicMock
import pytest

from ble_exporter.main import aggregate_scan_results


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock(spec=logging.Logger)
    return logger


def test_aggregate_single_device_single_packet(mock_logger):
    """Test aggregation with one device and one complete packet."""
    # BTHome packet with temp + humidity + battery
    packet = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
        0x03, 0xBF, 0x28,  # Humidity: 104.31%
        0x0A, 0x55,        # Battery: 85%
    ])

    scan_results = [
        ("A4:C1:38:11:22:33", packet)
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["humidity"] == pytest.approx(104.31, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["battery"] == pytest.approx(85.0, abs=0.01)

    # No warnings should be logged
    mock_logger.warning.assert_not_called()


def test_aggregate_single_device_alternating_packets(mock_logger):
    """Test aggregation when device sends temp/humidity in one packet, battery in another."""
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

    scan_results = [
        ("A4:C1:38:11:22:33", packet1),
        ("A4:C1:38:11:22:33", packet2),
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Should have merged both packets
    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["humidity"] == pytest.approx(104.31, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["battery"] == pytest.approx(93.9, abs=0.5)

    mock_logger.warning.assert_not_called()


def test_aggregate_multiple_devices(mock_logger):
    """Test aggregation with multiple devices."""
    packet1 = bytes([0x02, 0x02, 0x66, 0x08])  # Temp: 21.5°C
    packet2 = bytes([0x02, 0x03, 0xBF, 0x28])  # Humidity: 104.31%
    packet3 = bytes([0x02, 0x0A, 0x32])        # Battery: 50%

    scan_results = [
        ("A4:C1:38:11:22:33", packet1),
        ("A4:C1:38:44:55:66", packet2),
        ("A4:C1:38:11:22:33", packet3),
    ]

    known_macs = {"A4:C1:38:11:22:33", "A4:C1:38:44:55:66"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Device 1 should have temp + battery
    assert "A4:C1:38:11:22:33" in result
    assert "temperature" in result["A4:C1:38:11:22:33"]
    assert "battery" in result["A4:C1:38:11:22:33"]
    assert "humidity" not in result["A4:C1:38:11:22:33"]

    # Device 2 should have only humidity
    assert "A4:C1:38:44:55:66" in result
    assert "humidity" in result["A4:C1:38:44:55:66"]
    assert "temperature" not in result["A4:C1:38:44:55:66"]

    mock_logger.warning.assert_not_called()


def test_aggregate_all_parses_fail_for_known_device(mock_logger):
    """Test that warning is logged when all packets from known device fail to parse."""
    # Invalid packets (too short)
    invalid_packet1 = bytes([0x02])
    invalid_packet2 = bytes([0x02, 0xFF])

    scan_results = [
        ("A4:C1:38:11:22:33", invalid_packet1),
        ("A4:C1:38:11:22:33", invalid_packet2),
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Device should NOT be in result (all parses failed)
    assert "A4:C1:38:11:22:33" not in result

    # Warning should be logged
    mock_logger.warning.assert_called_once()
    warning_msg = mock_logger.warning.call_args[0][0]
    assert "A4:C1:38:11:22:33" in warning_msg
    assert "all packets failed to parse" in warning_msg.lower()


def test_aggregate_all_parses_fail_for_unknown_device(mock_logger):
    """Test that no warning is logged when unknown device fails to parse."""
    # Invalid packet
    invalid_packet = bytes([0x02])

    scan_results = [
        ("FF:FF:FF:FF:FF:FF", invalid_packet),
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Unknown device not in result
    assert "FF:FF:FF:FF:FF:FF" not in result

    # No warning should be logged (unknown device)
    mock_logger.warning.assert_not_called()


def test_aggregate_partial_parse_failures(mock_logger):
    """Test device with mix of successful and failed parses."""
    # One valid packet
    valid_packet = bytes([0x02, 0x02, 0x66, 0x08])  # Temp: 21.5°C

    # One invalid packet
    invalid_packet = bytes([0x02])

    scan_results = [
        ("A4:C1:38:11:22:33", valid_packet),
        ("A4:C1:38:11:22:33", invalid_packet),
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Device should be in result (at least one successful parse)
    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)

    # No warning (at least one parse succeeded)
    mock_logger.warning.assert_not_called()


def test_aggregate_last_value_wins(mock_logger):
    """Test that when duplicate measurements exist, last value wins."""
    # Two packets with different temperatures
    packet1 = bytes([0x02, 0x02, 0x66, 0x08])  # Temp: 21.5°C
    packet2 = bytes([0x02, 0x02, 0x00, 0x0A])  # Temp: 25.6°C

    scan_results = [
        ("A4:C1:38:11:22:33", packet1),
        ("A4:C1:38:11:22:33", packet2),
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Should have the last (most recent) temperature
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(25.6, abs=0.01)


def test_aggregate_empty_scan_results(mock_logger):
    """Test aggregation with no scan results."""
    scan_results = []
    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Result should be empty
    assert result == {}

    # No warnings
    mock_logger.warning.assert_not_called()


def test_aggregate_no_known_macs(mock_logger):
    """Test aggregation when no MACs are configured."""
    packet = bytes([0x02, 0x02, 0x66, 0x08])

    scan_results = [
        ("A4:C1:38:11:22:33", packet),
    ]

    known_macs = set()

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Device should NOT be in result (early filtering skips unknown MACs)
    assert "A4:C1:38:11:22:33" not in result
    assert result == {}

    # No warnings (not a known device)
    mock_logger.warning.assert_not_called()


def test_aggregate_unknown_device_with_valid_packet(mock_logger):
    """Test that unknown devices are filtered out early."""
    packet = bytes([0x02, 0x02, 0x66, 0x08])  # Temp: 21.5°C

    scan_results = [
        ("FF:FF:FF:FF:FF:FF", packet),  # Unknown device
    ]

    known_macs = {"A4:C1:38:11:22:33"}

    result = aggregate_scan_results(scan_results, known_macs, mock_logger)

    # Unknown device should NOT be in result (early filtering)
    assert "FF:FF:FF:FF:FF:FF" not in result
    assert result == {}

    # No warnings (unknown device)
    mock_logger.warning.assert_not_called()
