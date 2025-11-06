"""
Tests for BLE diagnostic tool.
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from ble_exporter.diagnostics import DiagnosticScanner, Advertisement


@pytest.fixture
def mock_device():
    """Create a mock BLE device."""
    device = MagicMock()
    device.address = "A4:C1:38:B6:36:7A"
    return device


@pytest.fixture
def mock_ad_data_bthome_v2():
    """Create mock advertisement data with valid BTHome v2 packet."""
    ad_data = MagicMock()
    ad_data.rssi = -45
    # BTHome v2 packet: temp=25.0°C, humidity=60.5%
    ad_data.service_data = {
        "0000181a-0000-1000-8000-00805f9b34fb": bytes([0x02, 0x02, 0xC8, 0x09, 0x03, 0xD5, 0x17])
    }
    ad_data.manufacturer_data = {}
    return ad_data


@pytest.fixture
def mock_ad_data_custom_format():
    """Create mock advertisement data with custom (non-BTHome) format.

    This packet has only unknown object IDs, so it will fail to parse
    with "No valid sensor data found in packet".
    """
    ad_data = MagicMock()
    ad_data.rssi = -50
    # Packet with only unknown object IDs (no temp/humidity/battery/voltage)
    ad_data.service_data = {
        "0000181a-0000-1000-8000-00805f9b34fb": bytes([0x40, 0xFF, 0xAA, 0xEE, 0xBB])
    }
    ad_data.manufacturer_data = {
        1234: bytes([0x01, 0x02, 0x03])
    }
    return ad_data


def test_diagnostic_scanner_initialization():
    """Test DiagnosticScanner initialization."""
    scanner = DiagnosticScanner("a4:c1:38:b6:36:7a")

    assert scanner.target_mac == "A4:C1:38:B6:36:7A"  # Normalized to uppercase
    assert scanner.quiet is False
    assert scanner.advertisements == []
    assert scanner.running is True


def test_diagnostic_scanner_quiet_mode():
    """Test DiagnosticScanner in quiet mode."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    assert scanner.quiet is True


def test_detection_callback_with_bthome_v2(mock_device, mock_ad_data_bthome_v2):
    """Test detection callback with valid BTHome v2 packet."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)

    assert len(scanner.advertisements) == 1
    ad = scanner.advertisements[0]

    assert ad.rssi == -45
    assert "0000181a-0000-1000-8000-00805f9b34fb" in ad.service_data
    assert ad.parse_result["success"] is True
    assert "measurements" in ad.parse_result
    assert "temperature" in ad.parse_result["measurements"]


def test_detection_callback_with_custom_format(mock_device, mock_ad_data_custom_format):
    """Test detection callback with custom (non-BTHome) format."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    scanner._detection_callback(mock_device, mock_ad_data_custom_format)

    assert len(scanner.advertisements) == 1
    ad = scanner.advertisements[0]

    assert ad.rssi == -50
    assert ad.parse_result["success"] is False
    assert "error" in ad.parse_result
    assert ad.manufacturer_data[1234] == "010203"


def test_detection_callback_ignores_other_devices():
    """Test that detection callback ignores advertisements from other devices."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    wrong_device = MagicMock()
    wrong_device.address = "FF:FF:FF:FF:FF:FF"

    ad_data = MagicMock()
    ad_data.rssi = -45
    ad_data.service_data = {}
    ad_data.manufacturer_data = {}

    scanner._detection_callback(wrong_device, ad_data)

    assert len(scanner.advertisements) == 0


def test_get_statistics_empty():
    """Test statistics calculation with no advertisements."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    stats = scanner.get_statistics()

    assert stats["total_advertisements"] == 0
    assert stats["parse_success_rate"] == 0.0
    assert stats["average_rssi"] == 0.0
    assert stats["service_uuids_seen"] == []


def test_get_statistics_with_data(mock_device, mock_ad_data_bthome_v2, mock_ad_data_custom_format):
    """Test statistics calculation with mixed successful and failed parses."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    # Add one successful and one failed advertisement
    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)
    scanner._detection_callback(mock_device, mock_ad_data_custom_format)

    stats = scanner.get_statistics()

    assert stats["total_advertisements"] == 2
    assert stats["successful_parses"] == 1
    assert stats["failed_parses"] == 1
    assert stats["parse_success_rate"] == 0.5
    assert stats["average_rssi"] == -47.5  # Average of -45 and -50
    assert "0000181a-0000-1000-8000-00805f9b34fb" in stats["service_uuids_seen"]


def test_save_json_with_custom_filename(tmp_path, mock_device, mock_ad_data_bthome_v2):
    """Test JSON save with custom filename."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)
    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)

    output_file = tmp_path / "test_output.json"
    saved_path = scanner.save_json(str(output_file))

    assert saved_path == str(output_file)
    assert output_file.exists()

    # Verify JSON structure
    with open(output_file) as f:
        data = json.load(f)

    assert data["mac_address"] == "A4:C1:38:B6:36:7A"
    assert "advertisements" in data
    assert len(data["advertisements"]) == 1
    assert "statistics" in data


def test_save_json_with_auto_filename(tmp_path, mock_device, mock_ad_data_bthome_v2, monkeypatch):
    """Test JSON save with auto-generated filename."""
    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)
    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)

    saved_path = scanner.save_json()

    # Check filename format: ble_diagnostics_A4C138B6367A_YYYYMMDD_HHMMSS.json
    assert saved_path.startswith("ble_diagnostics_A4C138B6367A_")
    assert saved_path.endswith(".json")
    assert (tmp_path / saved_path).exists()


def test_advertisement_dataclass():
    """Test Advertisement dataclass creation."""
    ad = Advertisement(
        timestamp="2025-11-03T14:23:15.123",
        rssi=-45,
        service_data={"uuid1": "aabbcc"},
        manufacturer_data={1234: "010203"},
        parse_result={"success": True}
    )

    assert ad.timestamp == "2025-11-03T14:23:15.123"
    assert ad.rssi == -45
    assert ad.service_data["uuid1"] == "aabbcc"
    assert ad.manufacturer_data[1234] == "010203"
    assert ad.parse_result["success"] is True


@pytest.mark.asyncio
async def test_scan_with_duration():
    """Test scan method with duration parameter."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    with patch('ble_exporter.diagnostics.BleakScanner') as mock_scanner_class:
        mock_scanner_instance = AsyncMock()
        mock_scanner_class.return_value = mock_scanner_instance

        # Run scan for 1 second
        await scanner.scan(duration=1)

        # Verify scanner was started and stopped
        mock_scanner_instance.start.assert_called_once()
        mock_scanner_instance.stop.assert_called_once()


def test_display_advertisement_success(capsys, mock_device, mock_ad_data_bthome_v2):
    """Test console display for successful parse."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=False)

    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)

    captured = capsys.readouterr()
    assert "RSSI: -45 dBm" in captured.out
    assert "Service UUID:" in captured.out
    assert "BTHome parse: ✅ SUCCESS" in captured.out
    assert "Temperature:" in captured.out


def test_display_advertisement_failure(capsys, mock_device, mock_ad_data_custom_format):
    """Test console display for failed parse."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=False)

    scanner._detection_callback(mock_device, mock_ad_data_custom_format)

    captured = capsys.readouterr()
    assert "RSSI: -50 dBm" in captured.out
    assert "Service UUID:" in captured.out
    assert "BTHome parse: ❌ FAILED" in captured.out
    assert "Manufacturer ID: 1234" in captured.out


def test_quiet_mode_suppresses_output(capsys, mock_device, mock_ad_data_bthome_v2):
    """Test that quiet mode suppresses console output."""
    scanner = DiagnosticScanner("A4:C1:38:B6:36:7A", quiet=True)

    scanner._detection_callback(mock_device, mock_ad_data_bthome_v2)

    captured = capsys.readouterr()
    assert captured.out == ""  # No console output in quiet mode
