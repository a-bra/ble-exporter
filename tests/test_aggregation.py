# ABOUTME: Tests for measurement aggregation logic
# ABOUTME: Tests grouping and merging of BLE packets by MAC address
import logging
import struct
from unittest.mock import MagicMock
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

from ble_exporter.config import DeviceConfig
from ble_exporter.main import aggregate_scan_results


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock(spec=logging.Logger)
    return logger


def test_aggregate_single_device_single_packet(mock_logger):
    """Test aggregation with one device and one complete packet."""
    # BTHome packet with temp + humidity + battery (from voltage)
    packet = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
        0x03, 0xBF, 0x28,  # Humidity: 104.31%
        0x0C, 0x50, 0x0B,  # Voltage: 2896mV -> ~89.6% battery
    ])

    scan_results = [
        ("A4:C1:38:11:22:33", packet)
    ]

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["humidity"] == pytest.approx(104.31, abs=0.01)
    assert result["A4:C1:38:11:22:33"]["battery"] == pytest.approx(89.6, abs=0.5)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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
    packet3 = bytes([0x02, 0x0C, 0xC4, 0x09])  # Voltage: 2500mV -> ~50% battery

    scan_results = [
        ("A4:C1:38:11:22:33", packet1),
        ("A4:C1:38:44:55:66", packet2),
        ("A4:C1:38:11:22:33", packet3),
    ]

    devices = {
        "A4:C1:38:11:22:33": DeviceConfig(name="device_1"),
        "A4:C1:38:44:55:66": DeviceConfig(name="device_2"),
    }

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    # Should have the last (most recent) temperature
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(25.6, abs=0.01)


def test_aggregate_empty_scan_results(mock_logger):
    """Test aggregation with no scan results."""
    scan_results = []
    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

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

    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    # Unknown device should NOT be in result (early filtering)
    assert "FF:FF:FF:FF:FF:FF" not in result
    assert result == {}

    # No warnings (unknown device)
    mock_logger.warning.assert_not_called()


def test_aggregate_empty_payload_does_not_crash(mock_logger):
    """Test that an empty payload is skipped without crashing the aggregation."""
    valid_packet = bytes([0x02, 0x02, 0x66, 0x08])  # Temp: 21.5°C
    empty_packet = b""

    scan_results = [
        ("A4:C1:38:11:22:33", empty_packet),
        ("A4:C1:38:11:22:33", valid_packet),
    ]
    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="test_device")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)


# --- Encrypted device aggregation tests ---

SYNTH_BINDKEY = "11223344556677889900aabbccddeeff"


def _encrypt_payload(plaintext: bytes, mac: str, bindkey_hex: str, counter: int = 1) -> bytes:
    """Helper: build encrypted BTHome frame from plaintext objects."""
    key = bytes.fromhex(bindkey_hex)
    device_info = bytes([0x41])
    counter_bytes = struct.pack('<I', counter)
    mac_bytes = bytes(int(b, 16) for b in mac.split(':'))
    nonce = mac_bytes + b'\xD2\xFC' + device_info + counter_bytes
    aesccm = AESCCM(key, tag_length=4)
    ct_and_mic = aesccm.encrypt(nonce, plaintext, b"")
    return device_info + ct_and_mic[:-4] + counter_bytes + ct_and_mic[-4:]


def test_aggregate_encrypted_device(mock_logger):
    """Test that encrypted packets are decrypted and parsed correctly."""
    plaintext = bytes([0x02, 0x66, 0x08])  # Temperature: 21.5°C
    encrypted_packet = _encrypt_payload(plaintext, "A4:C1:38:11:22:33", SYNTH_BINDKEY)

    scan_results = [("A4:C1:38:11:22:33", encrypted_packet)]
    devices = {
        "A4:C1:38:11:22:33": DeviceConfig(
            name="encrypted_sensor", bindkey=SYNTH_BINDKEY
        ),
    }

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    assert "A4:C1:38:11:22:33" in result
    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)
    mock_logger.warning.assert_not_called()


def test_aggregate_mixed_encrypted_and_plain(mock_logger):
    """Test aggregation with both encrypted and unencrypted devices."""
    plain_packet = bytes([0x02, 0x02, 0x66, 0x08])  # Unencrypted temp: 21.5°C

    enc_plaintext = bytes([0x02, 0x00, 0x0A])  # Temperature: 25.6°C
    encrypted_packet = _encrypt_payload(enc_plaintext, "A4:C1:38:44:55:66", SYNTH_BINDKEY)

    scan_results = [
        ("A4:C1:38:11:22:33", plain_packet),
        ("A4:C1:38:44:55:66", encrypted_packet),
    ]
    devices = {
        "A4:C1:38:11:22:33": DeviceConfig(name="plain_sensor"),
        "A4:C1:38:44:55:66": DeviceConfig(
            name="encrypted_sensor", bindkey=SYNTH_BINDKEY
        ),
    }

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    assert result["A4:C1:38:11:22:33"]["temperature"] == pytest.approx(21.5, abs=0.01)
    assert result["A4:C1:38:44:55:66"]["temperature"] == pytest.approx(25.6, abs=0.01)


def test_aggregate_encrypted_frame_without_bindkey_warns(mock_logger):
    """Test that encrypted frame from device without bindkey logs a warning."""
    # Build an encrypted frame (device_info 0x41) but device has no bindkey
    encrypted_packet = bytes([0x41, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF,
                              0x01, 0x00, 0x00, 0x00, 0x11, 0x22, 0x33, 0x44])

    scan_results = [("A4:C1:38:11:22:33", encrypted_packet)]
    devices = {"A4:C1:38:11:22:33": DeviceConfig(name="no_key_sensor")}

    result = aggregate_scan_results(scan_results, devices, mock_logger)

    assert "A4:C1:38:11:22:33" not in result

    mock_logger.warning.assert_called()
    warning_msgs = [call[0][0].lower() for call in mock_logger.warning.call_args_list]
    assert any("encrypted" in msg and "bindkey" in msg for msg in warning_msgs)
