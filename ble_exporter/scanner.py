# ABOUTME: BLE scanning abstraction for passive advertisement listening
# ABOUTME: Provides Protocol interface and MockScanner for testing without hardware
from typing import Protocol, Optional
import asyncio


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

    This is a placeholder for future implementation.
    """

    async def scan(self, duration_s: int) -> list[tuple[str, bytes]]:
        """
        Scan for BLE advertisements using bleak.

        Args:
            duration_s: Duration to scan in seconds

        Returns:
            List of (mac_address, payload_bytes) tuples

        Raises:
            NotImplementedError: This is a placeholder
        """
        raise NotImplementedError("BleakScannerImpl not yet implemented")


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
