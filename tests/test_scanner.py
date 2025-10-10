# ABOUTME: Unit tests for BLE scanner abstraction
# ABOUTME: Tests MockScanner functionality and get_scanner factory function
import pytest

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
async def test_bleak_scanner_not_implemented():
    """Test that BleakScannerImpl raises NotImplementedError."""
    scanner = BleakScannerImpl()

    with pytest.raises(NotImplementedError, match="BleakScannerImpl not yet implemented"):
        await scanner.scan(duration_s=5)


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
