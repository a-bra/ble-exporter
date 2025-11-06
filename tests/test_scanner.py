# ABOUTME: Unit tests for BLE scanner abstraction
# ABOUTME: Tests MockScanner functionality and get_scanner factory function
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ble_exporter.scanner import MockScanner, get_scanner, BleakScannerImpl


@pytest.mark.asyncio
async def test_mock_scanner_returns_configured_data():
    """Test that MockScanner returns the data it was configured with."""
    test_data = [
        ("A4:C1:38:11:22:33", bytes([0x40, 0x02, 0x66, 0x08])),
        ("A4:C1:38:44:55:66", bytes([0x40, 0x03, 0x8C, 0x19])),
    ]

    scanner = MockScanner(data=test_data)
    result = await scanner.scan(duration_s=5)

    assert len(result) == 2
    assert result[0] == ("A4:C1:38:11:22:33", bytes([0x40, 0x02, 0x66, 0x08]))
    assert result[1] == ("A4:C1:38:44:55:66", bytes([0x40, 0x03, 0x8C, 0x19]))


@pytest.mark.asyncio
async def test_mock_scanner_returns_copy_of_data():
    """Test that MockScanner returns a copy, not the original list."""
    test_data = [("AA:BB:CC:DD:EE:FF", bytes([0x40, 0x0A, 0x64]))]

    scanner = MockScanner(data=test_data)
    result1 = await scanner.scan(duration_s=5)
    result2 = await scanner.scan(duration_s=5)

    # Modify first result
    result1.append(("11:22:33:44:55:66", bytes([0xFF])))

    # Second result should be unaffected
    assert len(result2) == 1
    assert result2[0] == ("AA:BB:CC:DD:EE:FF", bytes([0x40, 0x0A, 0x64]))


@pytest.mark.asyncio
async def test_mock_scanner_empty_data():
    """Test MockScanner with no data returns empty list."""
    scanner = MockScanner(data=[])
    result = await scanner.scan(duration_s=5)

    assert result == []


@pytest.mark.asyncio
async def test_mock_scanner_default_empty():
    """Test MockScanner defaults to empty data if not provided."""
    scanner = MockScanner()
    result = await scanner.scan(duration_s=5)

    assert result == []


@pytest.mark.asyncio
async def test_mock_scanner_ignores_duration():
    """Test that MockScanner returns same data regardless of duration."""
    test_data = [("AA:BB:CC:DD:EE:FF", bytes([0x40]))]
    scanner = MockScanner(data=test_data)

    result1 = await scanner.scan(duration_s=1)
    result2 = await scanner.scan(duration_s=10)

    assert result1 == result2


def test_get_scanner_returns_mock_when_requested():
    """Test that get_scanner returns MockScanner when use_mock=True."""
    test_data = [("AA:BB:CC:DD:EE:FF", bytes([0x40]))]
    scanner = get_scanner(use_mock=True, data=test_data)

    assert isinstance(scanner, MockScanner)
    assert scanner.data == test_data


def test_get_scanner_returns_bleak_by_default():
    """Test that get_scanner returns BleakScannerImpl by default."""
    scanner = get_scanner(use_mock=False)

    assert isinstance(scanner, BleakScannerImpl)


def test_get_scanner_mock_with_no_data():
    """Test that get_scanner can create MockScanner without data."""
    scanner = get_scanner(use_mock=True)

    assert isinstance(scanner, MockScanner)
    assert scanner.data == []


@pytest.mark.asyncio
async def test_bleak_scanner_basic_scan():
    """Test that BleakScannerImpl can perform a basic scan."""
    scanner = BleakScannerImpl()

    # Mock BleakScanner
    with patch('ble_exporter.scanner.BleakScanner') as mock_scanner_class:
        mock_scanner_instance = AsyncMock()
        mock_scanner_class.return_value = mock_scanner_instance

        # Simulate a short scan
        result = await scanner.scan(duration_s=1)

        # Verify scanner was started and stopped
        mock_scanner_instance.start.assert_called_once()
        mock_scanner_instance.stop.assert_called_once()

        # Result should be a list (empty in this case since no devices detected)
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_bleak_scanner_detection_callback():
    """Test that BleakScannerImpl properly processes detected devices."""
    scanner = BleakScannerImpl()

    # Create mock device and advertisement data
    mock_device = MagicMock()
    mock_device.address = "A4:C1:38:11:22:33"

    mock_ad_data = MagicMock()
    # Simulate service data with BTHome packet
    mock_ad_data.service_data = {
        "0000181a-0000-1000-8000-00805f9b34fb": bytes([0x02, 0x02, 0x66, 0x08])
    }

    # Call detection callback directly
    scanner._detection_callback(mock_device, mock_ad_data)

    # Verify the advertisement was stored
    assert len(scanner.advertisements) == 1
    assert scanner.advertisements[0][0] == "A4:C1:38:11:22:33"
    assert scanner.advertisements[0][1] == bytes([0x02, 0x02, 0x66, 0x08])


@pytest.mark.asyncio
async def test_bleak_scanner_multiple_devices():
    """Test that BleakScannerImpl handles multiple devices."""
    scanner = BleakScannerImpl()

    # Create mock devices
    device1 = MagicMock()
    device1.address = "A4:C1:38:11:22:33"
    ad_data1 = MagicMock()
    ad_data1.service_data = {"uuid1": bytes([0x02, 0x02, 0x66, 0x08])}

    device2 = MagicMock()
    device2.address = "A4:C1:38:44:55:66"
    ad_data2 = MagicMock()
    ad_data2.service_data = {"uuid2": bytes([0x02, 0x0A, 0x55])}

    # Call detection callbacks
    scanner._detection_callback(device1, ad_data1)
    scanner._detection_callback(device2, ad_data2)

    # Verify both devices were stored
    assert len(scanner.advertisements) == 2
    macs = [mac for mac, _ in scanner.advertisements]
    assert "A4:C1:38:11:22:33" in macs
    assert "A4:C1:38:44:55:66" in macs


@pytest.mark.asyncio
async def test_bleak_scanner_empty_service_data():
    """Test that BleakScannerImpl ignores devices without service data."""
    scanner = BleakScannerImpl()

    mock_device = MagicMock()
    mock_device.address = "A4:C1:38:11:22:33"

    mock_ad_data = MagicMock()
    mock_ad_data.service_data = {}  # Empty service data

    # Call detection callback
    scanner._detection_callback(mock_device, mock_ad_data)

    # Verify no advertisements were stored
    assert len(scanner.advertisements) == 0


@pytest.mark.asyncio
async def test_bleak_scanner_no_service_data():
    """Test that BleakScannerImpl handles advertisements with no service data."""
    scanner = BleakScannerImpl()

    mock_device = MagicMock()
    mock_device.address = "A4:C1:38:11:22:33"

    mock_ad_data = MagicMock()
    mock_ad_data.service_data = None  # No service data

    # Call detection callback
    scanner._detection_callback(mock_device, mock_ad_data)

    # Verify no advertisements were stored
    assert len(scanner.advertisements) == 0


@pytest.mark.asyncio
async def test_bleak_scanner_clears_previous_results():
    """Test that BleakScannerImpl clears results between scans."""
    scanner = BleakScannerImpl()

    # Add some fake data to advertisements
    scanner.advertisements.append(("AA:BB:CC:DD:EE:FF", bytes([0xFF])))

    with patch('ble_exporter.scanner.BleakScanner') as mock_scanner_class:
        mock_scanner_instance = AsyncMock()
        mock_scanner_class.return_value = mock_scanner_instance

        # Perform a new scan
        await scanner.scan(duration_s=1)

        # Previous results should be cleared
        assert len(scanner.advertisements) == 0


@pytest.mark.asyncio
async def test_bleak_scanner_handles_scan_error():
    """Test that BleakScannerImpl raises RuntimeError on scan failure."""
    scanner = BleakScannerImpl()

    with patch('ble_exporter.scanner.BleakScanner') as mock_scanner_class:
        mock_scanner_instance = AsyncMock()
        mock_scanner_instance.start.side_effect = Exception("BLE adapter not found")
        mock_scanner_class.return_value = mock_scanner_instance

        # Scan should raise RuntimeError
        with pytest.raises(RuntimeError, match="BLE scan failed"):
            await scanner.scan(duration_s=1)


@pytest.mark.asyncio
async def test_mock_scanner_multiple_devices():
    """Test MockScanner with multiple different devices."""
    test_data = [
        ("A4:C1:38:11:22:33", bytes([0x40, 0x02, 0x66, 0x08, 0x03, 0x8C, 0x19])),
        ("A4:C1:38:44:55:66", bytes([0x40, 0x0A, 0x55])),
        ("A4:C1:38:77:88:99", bytes([0x40, 0x02, 0xE6, 0xFB])),
    ]

    scanner = MockScanner(data=test_data)
    result = await scanner.scan(duration_s=5)

    assert len(result) == 3
    assert result[0][0] == "A4:C1:38:11:22:33"
    assert result[1][0] == "A4:C1:38:44:55:66"
    assert result[2][0] == "A4:C1:38:77:88:99"


@pytest.mark.asyncio
async def test_bleak_scanner_multiple_packets_same_device():
    """Test that BleakScannerImpl collects multiple packets from same MAC.

    This simulates real sensor behavior where the same device sends multiple
    advertisements during the scan period (alternating between temp/humidity
    and battery packets).
    """
    scanner = BleakScannerImpl()

    # Create mock device
    device = MagicMock()
    device.address = "A4:C1:38:11:22:33"

    # First packet: temp + humidity
    ad_data1 = MagicMock()
    ad_data1.service_data = {"uuid1": bytes([0x02, 0x02, 0x66, 0x08, 0x03, 0xBF, 0x28])}

    # Second packet: battery (from same device)
    ad_data2 = MagicMock()
    ad_data2.service_data = {"uuid1": bytes([0x02, 0x0A, 0x55])}

    # Call detection callbacks twice for same device
    scanner._detection_callback(device, ad_data1)
    scanner._detection_callback(device, ad_data2)

    # Verify BOTH packets were collected (not overwritten)
    assert len(scanner.advertisements) == 2
    assert scanner.advertisements[0][0] == "A4:C1:38:11:22:33"
    assert scanner.advertisements[1][0] == "A4:C1:38:11:22:33"
    assert scanner.advertisements[0][1] == bytes([0x02, 0x02, 0x66, 0x08, 0x03, 0xBF, 0x28])
    assert scanner.advertisements[1][1] == bytes([0x02, 0x0A, 0x55])
