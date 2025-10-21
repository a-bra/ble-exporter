# ABOUTME: BLE scanning abstraction for passive advertisement listening
# ABOUTME: Provides Protocol interface and MockScanner for testing without hardware
from typing import Protocol, Optional
import asyncio
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


class AbstractScanner(Protocol):
    """Protocol for BLE scanners that return MAC address and payload tuples."""

    async def scan(self, duration_s: int) -> list[tuple[str, bytes]]:
        """
        Scan for BLE advertisements for the specified duration.

        Args:
            duration_s: Duration to scan in seconds

        Returns:
            List of (mac_address, payload_bytes) tuples
        """
        ...


class BleakScannerImpl:
    """
    Real BLE scanner implementation using bleak library.

    Scans for BLE advertisements and extracts service data containing BTHome packets.
    """

    def __init__(self):
        """Initialize the BLE scanner."""
        self.advertisements: dict[str, bytes] = {}

    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """
        Callback invoked when a BLE advertisement is detected.

        Extracts service data (which contains BTHome packets for ATC_MiThermometer devices)
        and stores it keyed by MAC address.

        Args:
            device: BLE device information
            advertisement_data: Advertisement data including service data
        """
        mac_address = device.address

        # BTHome data is typically in service_data
        # ATC_MiThermometer with BTHome uses service UUID 0x181A or custom UUIDs
        # We collect all service data and let the parser validate it
        if advertisement_data.service_data:
            # Take the first service data entry
            # BTHome packets are self-describing with version byte at start
            for uuid, data in advertisement_data.service_data.items():
                if data:
                    self.advertisements[mac_address] = bytes(data)
                    break

    async def scan(self, duration_s: int) -> list[tuple[str, bytes]]:
        """
        Scan for BLE advertisements using bleak.

        Args:
            duration_s: Duration to scan in seconds

        Returns:
            List of (mac_address, payload_bytes) tuples containing service data

        Raises:
            RuntimeError: If BLE adapter is unavailable or scanning fails
        """
        # Clear previous scan results
        self.advertisements = {}

        try:
            # Create scanner with detection callback
            scanner = BleakScanner(detection_callback=self._detection_callback)

            # Start scanning
            await scanner.start()

            # Scan for specified duration
            await asyncio.sleep(duration_s)

            # Stop scanning
            await scanner.stop()

        except Exception as e:
            raise RuntimeError(f"BLE scan failed: {e}") from e

        # Convert dict to list of tuples
        return list(self.advertisements.items())


class MockScanner:
    """
    Mock BLE scanner for testing without hardware.

    Returns preconfigured list of (MAC, payload) tuples on each scan() call.
    """

    def __init__(self, data: Optional[list[tuple[str, bytes]]] = None):
        """
        Initialize mock scanner with test data.

        Args:
            data: List of (mac_address, payload_bytes) tuples to return on scan
        """
        self.data = data or []

    async def scan(self, duration_s: int) -> list[tuple[str, bytes]]:
        """
        Return preconfigured mock data.

        Args:
            duration_s: Duration parameter (ignored in mock)

        Returns:
            List of (mac_address, payload_bytes) tuples
        """
        # Simulate async behavior with small delay
        await asyncio.sleep(0.01)
        return self.data.copy()


def get_scanner(use_mock: bool = False, data: Optional[list[tuple[str, bytes]]] = None) -> AbstractScanner:
    """
    Factory function to get appropriate scanner implementation.

    Args:
        use_mock: If True, return MockScanner; otherwise return BleakScannerImpl
        data: Test data for MockScanner (only used when use_mock=True)

    Returns:
        Scanner instance implementing AbstractScanner protocol
    """
    if use_mock:
        return MockScanner(data)
    else:
        return BleakScannerImpl()
