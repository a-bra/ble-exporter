# ABOUTME: BTHome packet parser for BLE advertisements
# ABOUTME: Decodes temperature, humidity, and battery from BTHome format packets
import struct


def parse_bthome(payload: bytes) -> dict[str, float]:
    """
    Parse BTHome format BLE advertisement packet.

    Extracts temperature, humidity, and battery level from BTHome v2 packets.
    BTHome format: https://bthome.io/format/

    Args:
        payload: Raw BTHome packet bytes

    Returns:
        Dictionary with sensor readings:
        - 'temperature': Temperature in Celsius
        - 'humidity': Relative humidity in percent
        - 'battery': Battery level in percent

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
            result['temperature'] = temp_raw * 0.01
            idx += 2

        # Humidity: 0x03, unsigned int16, little-endian, factor 0.01
        elif object_id == 0x03:
            if idx + 2 > len(payload):
                raise ValueError("Incomplete humidity data")
            humidity_raw = struct.unpack('<H', payload[idx:idx+2])[0]
            result['humidity'] = humidity_raw * 0.01
            idx += 2

        # Battery: 0x0A, unsigned int8, factor 1
        elif object_id == 0x0A:
            if idx + 1 > len(payload):
                raise ValueError("Incomplete battery data")
            result['battery'] = float(payload[idx])
            idx += 1

        else:
            # Unknown object ID - try to skip it
            # This is a simplified approach; real BTHome would need size lookup
            # For now, we'll try common sizes
            if object_id in [0x00, 0x01, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0B, 0x0C, 0x0D]:
                # These are typically 1-byte values
                idx += 1
            elif object_id in [0x04, 0x0E, 0x0F]:
                # These are typically 2-byte values
                idx += 2
            else:
                # Unknown size, skip to avoid infinite loop
                idx += 1

    if not result:
        raise ValueError("No valid sensor data found in packet")

    return result
