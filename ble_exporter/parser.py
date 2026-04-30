# ABOUTME: BTHome packet parser and decryptor for BLE advertisements
# ABOUTME: Decodes temperature, humidity, and battery from BTHome format packets
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESCCM


def decrypt_bthome(payload: bytes, mac: str, bindkey: str) -> bytes:
    """
    Decrypt an encrypted BTHome v2 advertisement frame.

    If the frame is not encrypted (device_info encryption bit clear),
    returns the payload unchanged.

    Args:
        payload: Raw BTHome frame bytes (device_info + ciphertext + counter + mic)
        mac: Device MAC address in "AA:BB:CC:DD:EE:FF" format
        bindkey: 32-character hex string (16-byte AES key)

    Returns:
        Decrypted BTHome frame with synthetic unencrypted device_info byte (0x40)

    Raises:
        ValueError: If frame is too short or decryption fails (wrong key/corrupted)
    """
    device_info = payload[0]

    if not (device_info & 0x01):
        return payload

    # Frame: device_info(1) || ciphertext(N) || counter(4 LE) || mic(4)
    if len(payload) < 10:
        raise ValueError("Encrypted BTHome frame too short (need device_info + counter + mic + data)")

    counter_bytes = payload[-8:-4]
    mic = payload[-4:]
    ciphertext = payload[1:-8]

    mac_bytes = bytes(int(b, 16) for b in mac.split(':'))
    nonce = mac_bytes + b'\xD2\xFC' + bytes([device_info]) + counter_bytes

    key = bytes.fromhex(bindkey)
    aesccm = AESCCM(key, tag_length=4)

    try:
        plaintext = aesccm.decrypt(nonce, ciphertext + mic, b"")
    except Exception as e:
        raise ValueError(f"Decryption failed for {mac}: {e}") from e

    return bytes([0x40]) + plaintext


def parse_bthome(payload: bytes) -> dict[str, float]:
    """
    Parse BTHome format BLE advertisement packet.

    Extracts temperature, humidity, and battery level from BTHome v2 packets.
    Battery is derived from voltage (0x0C) object using CR2032 discharge curve
    (3.0V=100%, 2.0V=0%). Designed for ATC_MiThermometer sensors.
    BTHome format: https://bthome.io/format/

    Args:
        payload: Raw BTHome packet bytes

    Returns:
        Dictionary with sensor readings:
        - 'temperature': Temperature in Celsius
        - 'humidity': Relative humidity in percent
        - 'battery': Battery level in percent (from voltage object)

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
            if object_id in [0x00, 0x01, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0D]:
                # These are typically 1-byte values (0x0A is battery %, not supported)
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
