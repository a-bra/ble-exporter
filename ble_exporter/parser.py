# ABOUTME: BTHome packet parser for BLE advertisements
# ABOUTME: Decodes temperature, humidity, and battery from BTHome format packets
import struct


def parse_bthome(payload: bytes) -> dict[str, float]:
    """
    Parse BTHome format BLE advertisement packet.

    Extracts temperature, humidity, and battery level from BTHome v2 packets.
    Supports both battery percentage (0x0A) and voltage (0x0C) objects.
    Voltage is converted to battery percentage using CR2032 curve (3.0V=100%, 2.0V=0%).
    BTHome format: https://bthome.io/format/

    Args:
        payload: Raw BTHome packet bytes

    Returns:
        Dictionary with sensor readings:
        - 'temperature': Temperature in Celsius
        - 'humidity': Relative humidity in percent
        - 'battery': Battery level in percent (from battery or voltage object)

    Raises:
        ValueError: If packet format is invalid or cannot be parsed
    """
    if len(payload) < 2:
        raise ValueError("Packet too short to be valid BTHome")

    result = {}

    # BTHome v2 format starts with device info byte
    # Skip the device info byte and parse object id/data pairs
    idx = 1

    while idx < len(payload):
        if idx >= len(payload):
            break

        object_id = payload[idx]
        idx += 1

        # Temperature: 0x02, signed int16, little-endian, factor 0.01
        if object_id == 0x02:
            if idx + 2 > len(payload):
                raise ValueError("Incomplete temperature data")
            temp_raw = struct.unpack('<h', payload[idx:idx+2])[0]
            result['temperature'] = round(temp_raw * 0.01, 2)
            idx += 2

        # Humidity: 0x03, unsigned int16, little-endian, factor 0.01
        elif object_id == 0x03:
            if idx + 2 > len(payload):
                raise ValueError("Incomplete humidity data")
            humidity_raw = struct.unpack('<H', payload[idx:idx+2])[0]
            result['humidity'] = round(humidity_raw * 0.01, 2)
            idx += 2

        # Battery: 0x0A, unsigned int8, factor 1
        elif object_id == 0x0A:
            if idx + 1 > len(payload):
                raise ValueError("Incomplete battery data")
            result['battery'] = float(payload[idx])
            idx += 1

        # Voltage: 0x0C, unsigned int16, little-endian, factor 0.001V
        # Convert to battery percentage using CR2032 voltage curve
        elif object_id == 0x0C:
            if idx + 2 > len(payload):
                raise ValueError("Incomplete voltage data")
            voltage_raw = struct.unpack('<H', payload[idx:idx+2])[0]
            voltage_v = voltage_raw * 0.001  # Convert to volts
            # CR2032: 3.0V (100%) to 2.0V (0%), linear approximation
            battery_pct = (voltage_v - 2.0) / (3.0 - 2.0) * 100
            # Clamp to 0-100% range
            result['battery'] = round(max(0.0, min(100.0, battery_pct)), 1)
            idx += 2

        else:
            # Unknown object ID - try to skip it
            # BTHome v2 object size mapping
            if object_id in [0x00, 0x01, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0B, 0x0D]:
                # These are typically 1-byte values
                idx += 1
            elif object_id in [0x04, 0x0E, 0x0F, 0x11]:
                # These are typically 2-byte values (0x11 is current)
                idx += 2
            elif object_id in [0x10]:
                # Power (0x10) is 3 bytes
                idx += 3
            else:
                # Unknown size, skip 1 byte to avoid infinite loop
                idx += 1

    if not result:
        raise ValueError(f"No valid sensor data found in packet - {payload}")

    return result
