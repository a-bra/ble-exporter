# ABOUTME: Unit tests for BTHome packet parser
# ABOUTME: Tests temperature, humidity, battery decoding and error handling
import pytest
from pytest import approx

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
    assert result['temperature'] == approx(21.5, abs=0.01)
    assert result['humidity'] == approx(65.4, abs=0.01)
    assert result['battery'] == approx(85.0, abs=0.01)


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
    assert result['temperature'] == approx(-10.5, abs=0.01)


def test_parse_temperature_only():
    """Test parsing packet with only temperature."""
    # Device info: 0x40
    # Temperature: 0x02 + 0x00 0x0A (25.6°C = 2560 * 0.01)
    packet = bytes([0x40, 0x02, 0x00, 0x0A])

    result = parse_bthome(packet)

    assert 'temperature' in result
    assert result['temperature'] == approx(25.6, abs=0.01)
    assert 'humidity' not in result
    assert 'battery' not in result


def test_parse_humidity_only():
    """Test parsing packet with only humidity."""
    # Device info: 0x40
    # Humidity: 0x03 + 0xC4 0x09 (25.0% = 2500 * 0.01)
    packet = bytes([0x40, 0x03, 0xC4, 0x09])

    result = parse_bthome(packet)

    assert 'humidity' in result
    assert result['humidity'] == approx(25.0, abs=0.01)
    assert 'temperature' not in result
    assert 'battery' not in result


def test_parse_battery_only():
    """Test parsing packet with only battery."""
    # Device info: 0x40
    # Battery: 0x0A + 0x64 (100%)
    packet = bytes([0x40, 0x0A, 0x64])

    result = parse_bthome(packet)

    assert 'battery' in result
    assert result['battery'] == approx(100.0, abs=0.01)
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
    assert result['temperature'] == approx(100.0, abs=0.01)
    assert result['battery'] == approx(50.0, abs=0.01)


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
    assert result['humidity'] == approx(99.99, abs=0.01)


def test_parse_zero_battery():
    """Test parsing zero battery value."""
    # Device info: 0x40
    # Battery: 0x0A + 0x00 (0%)
    packet = bytes([0x40, 0x0A, 0x00])

    result = parse_bthome(packet)

    assert 'battery' in result
    assert result['battery'] == approx(0.0, abs=0.01)


def test_parse_voltage_with_0x0a_in_data():
    """Test that voltage (0x0C) containing 0x0A doesn't get misread as battery.

    This tests the bug where voltage value 0x0AF8 (2808mV) was incorrectly
    parsed as battery 16% because 0x0A was treated as battery object ID.
    """
    # Device info: 0x40
    # Counter/padding: 0x00 0x21
    # Voltage: 0x0C + 0xF8 0x0A (2808mV = 0x0AF8)
    # Power: 0x10 + 0x00
    # Current: 0x11 + 0x01
    packet = bytes([0x40, 0x00, 0x21, 0x0C, 0xF8, 0x0A, 0x10, 0x00, 0x11, 0x01])

    result = parse_bthome(packet)

    # Should parse voltage, not incorrectly detect battery
    assert 'battery' in result
    # 2808mV = 2.808V -> approx 81% battery ((2.808-2.0)/(3.0-2.0)*100)
    assert result['battery'] == approx(80.8, abs=0.5)
    assert 'temperature' not in result
    assert 'humidity' not in result


def test_parse_voltage_only():
    """Test parsing packet with voltage (0x0C) converted to battery percentage."""
    # Device info: 0x40
    # Voltage: 0x0C + 0x7B 0x0B (2939mV = 0x0B7B = fresh battery ~75%)
    packet = bytes([0x40, 0x0C, 0x7B, 0x0B])

    result = parse_bthome(packet)

    assert 'battery' in result
    # 2939mV = 2.939V -> ~94% battery ((2.939-2.0)/(3.0-2.0)*100)
    assert result['battery'] == approx(93.9, abs=0.5)


def test_parse_voltage_depleted():
    """Test parsing low voltage (near 2.0V)."""
    # Device info: 0x40
    # Voltage: 0x0C + 0xD0 0x07 (2000mV = 0x07D0 = depleted)
    packet = bytes([0x40, 0x0C, 0xD0, 0x07])

    result = parse_bthome(packet)

    assert 'battery' in result
    # 2000mV = 2.0V -> 0% battery
    assert result['battery'] == approx(0.0, abs=0.5)


def test_parse_voltage_full():
    """Test parsing full voltage (3.0V)."""
    # Device info: 0x40
    # Voltage: 0x0C + 0xB8 0x0B (3000mV = 0x0BB8)
    packet = bytes([0x40, 0x0C, 0xB8, 0x0B])

    result = parse_bthome(packet)

    assert 'battery' in result
    # 3000mV = 3.0V -> 100% battery
    assert result['battery'] == approx(100.0, abs=0.5)


def test_parse_real_sensor_packet_with_voltage():
    """Test real packet from sensor that was failing: temp+humidity then voltage.

    This reproduces the actual diagnostic capture from the baby_room sensor.
    """
    # Real packet with temp and humidity
    packet1 = bytes([0x40, 0x00, 0x05, 0x01, 0x5C, 0x02, 0x88, 0x0A, 0x03, 0x9B, 0x14])
    result1 = parse_bthome(packet1)
    assert 'temperature' in result1
    assert 'humidity' in result1

    # Real packet with voltage that was failing to parse
    packet2 = bytes([0x40, 0x00, 0x05, 0x0C, 0x7B, 0x0B, 0x10, 0x00, 0x11, 0x01])
    result2 = parse_bthome(packet2)
    # Should successfully extract battery from voltage now
    assert 'battery' in result2
    assert result2['battery'] == approx(93.9, abs=1.0)
