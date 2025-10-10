# ABOUTME: Unit tests for BTHome packet parser
# ABOUTME: Tests temperature, humidity, battery decoding and error handling
import pytest

from ble_exporter.parser import parse_bthome


def test_parse_complete_packet():
    """Test parsing packet with temperature, humidity, and battery."""
    # Device info: 0x40
    # Temperature: 0x02 + 0x66 0x08 (21.5°C = 2150 * 0.01)
    # Humidity: 0x03 + 0x8C 0x19 (65.4% = 6540 * 0.01)
    # Battery: 0x0A + 0x55 (85%)
    packet = bytes([0x40, 0x02, 0x66, 0x08, 0x03, 0x8C, 0x19, 0x0A, 0x55])

    result = parse_bthome(packet)

    assert 'temperature' in result
    assert 'humidity' in result
    assert 'battery' in result
    assert abs(result['temperature'] - 21.5) < 0.01
    assert abs(result['humidity'] - 65.4) < 0.01
    assert abs(result['battery'] - 85.0) < 0.01


def test_parse_negative_temperature():
    """Test parsing packet with negative temperature."""
    # Device info: 0x40
    # Temperature: 0x02 + 0xF8 0xFF (-8°C = -800 * 0.01 = 0xFCE0 in int16)
    # Actually -8 * 100 = -800 = 0xFCE0 in little-endian = 0xE0 0xFC
    # Wait, -800 in signed int16:
    # -800 = 0xFCE0 (two's complement)
    # Little-endian: 0xE0 0xFC
    # But let me recalculate: -800 as int16 = -800 & 0xFFFF = 0xFCE0
    # In little-endian bytes: 0xE0, 0xFC
    # Actually -800 decimal = 0xFFFFFCE0 as signed, but as int16 = 0xFCE0
    # 0xFCE0 in little-endian = 0xE0 0xFC
    # Let me verify: struct.pack('<h', -800) would give us the bytes
    # Actually let me use a simpler example: -10.5°C = -1050
    # -1050 as int16 = 0xFBE6
    # Little-endian: 0xE6 0xFB
    packet = bytes([0x40, 0x02, 0xE6, 0xFB])

    result = parse_bthome(packet)

    assert 'temperature' in result
    assert abs(result['temperature'] - (-10.5)) < 0.01


def test_parse_temperature_only():
    """Test parsing packet with only temperature."""
    # Device info: 0x40
    # Temperature: 0x02 + 0x00 0x0A (25.6°C = 2560 * 0.01)
    packet = bytes([0x40, 0x02, 0x00, 0x0A])

    result = parse_bthome(packet)

    assert 'temperature' in result
    assert abs(result['temperature'] - 25.6) < 0.01
    assert 'humidity' not in result
    assert 'battery' not in result


def test_parse_humidity_only():
    """Test parsing packet with only humidity."""
    # Device info: 0x40
    # Humidity: 0x03 + 0xC4 0x09 (25.0% = 2500 * 0.01)
    packet = bytes([0x40, 0x03, 0xC4, 0x09])

    result = parse_bthome(packet)

    assert 'humidity' in result
    assert abs(result['humidity'] - 25.0) < 0.01
    assert 'temperature' not in result
    assert 'battery' not in result


def test_parse_battery_only():
    """Test parsing packet with only battery."""
    # Device info: 0x40
    # Battery: 0x0A + 0x64 (100%)
    packet = bytes([0x40, 0x0A, 0x64])

    result = parse_bthome(packet)

    assert 'battery' in result
    assert abs(result['battery'] - 100.0) < 0.01
    assert 'temperature' not in result
    assert 'humidity' not in result


def test_parse_with_unknown_objects():
    """Test parsing packet that includes unknown object IDs."""
    # Device info: 0x40
    # Unknown: 0x01 + 0xFF (ignore)
    # Temperature: 0x02 + 0x10 0x27 (100.0°C = 10000 * 0.01)
    # Unknown: 0xFF + 0xAA (ignore)
    # Battery: 0x0A + 0x32 (50%)
    packet = bytes([0x40, 0x01, 0xFF, 0x02, 0x10, 0x27, 0xFF, 0xAA, 0x0A, 0x32])

    result = parse_bthome(packet)

    assert 'temperature' in result
    assert 'battery' in result
    assert abs(result['temperature'] - 100.0) < 0.01
    assert abs(result['battery'] - 50.0) < 0.01


def test_parse_packet_too_short():
    """Test that packets shorter than 2 bytes raise ValueError."""
    packet = bytes([0x40])

    with pytest.raises(ValueError, match="Packet too short"):
        parse_bthome(packet)


def test_parse_empty_packet():
    """Test that empty packets raise ValueError."""
    packet = bytes([])

    with pytest.raises(ValueError, match="Packet too short"):
        parse_bthome(packet)


def test_parse_incomplete_temperature():
    """Test that incomplete temperature data raises ValueError."""
    # Device info: 0x40
    # Temperature: 0x02 + only 1 byte (should be 2)
    packet = bytes([0x40, 0x02, 0x6E])

    with pytest.raises(ValueError, match="Incomplete temperature data"):
        parse_bthome(packet)


def test_parse_incomplete_humidity():
    """Test that incomplete humidity data raises ValueError."""
    # Device info: 0x40
    # Humidity: 0x03 + only 1 byte (should be 2)
    packet = bytes([0x40, 0x03, 0x8C])

    with pytest.raises(ValueError, match="Incomplete humidity data"):
        parse_bthome(packet)


def test_parse_incomplete_battery():
    """Test that incomplete battery data raises ValueError."""
    # Device info: 0x40
    # Battery: 0x0A + no data (should be 1 byte)
    packet = bytes([0x40, 0x0A])

    with pytest.raises(ValueError, match="Incomplete battery data"):
        parse_bthome(packet)


def test_parse_no_valid_data():
    """Test that packet with only device info raises ValueError."""
    # Only device info, no sensor data
    packet = bytes([0x40, 0xFF, 0xAA, 0xFF, 0xBB])

    with pytest.raises(ValueError, match="No valid sensor data found"):
        parse_bthome(packet)


def test_parse_high_humidity():
    """Test parsing high humidity value (99.9%)."""
    # Device info: 0x40
    # Humidity: 0x03 + 0x0F 0x27 (99.99% = 9999 * 0.01)
    packet = bytes([0x40, 0x03, 0x0F, 0x27])

    result = parse_bthome(packet)

    assert 'humidity' in result
    assert abs(result['humidity'] - 99.99) < 0.01


def test_parse_zero_battery():
    """Test parsing zero battery value."""
    # Device info: 0x40
    # Battery: 0x0A + 0x00 (0%)
    packet = bytes([0x40, 0x0A, 0x00])

    result = parse_bthome(packet)

    assert 'battery' in result
    assert abs(result['battery'] - 0.0) < 0.01
