# ABOUTME: BLE diagnostic tool for troubleshooting sensor advertisements
# ABOUTME: Monitors specific MAC address and displays all advertisement data with BTHome parsing attempts
import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ble_exporter.parser import parse_bthome


@dataclass
class Advertisement:
    """Single BLE advertisement capture."""
    timestamp: str
    rssi: int
    service_data: dict[str, str]  # UUID -> hex string
    manufacturer_data: dict[int, str]  # Company ID -> hex string
    parse_result: dict  # success, error, or parsed data


class DiagnosticScanner:
    """
    BLE scanner for diagnostic purposes.

    Captures all advertisement data from a specific MAC address including
    RSSI, all service UUIDs, and attempts BTHome parsing.
    """

    def __init__(self, target_mac: str, quiet: bool = False):
        """
        Initialize diagnostic scanner.

        Args:
            target_mac: MAC address to monitor (case-insensitive)
            quiet: If True, suppress console output
        """
        self.target_mac = target_mac.upper()
        self.quiet = quiet
        self.advertisements: list[Advertisement] = []
        self.running = True

    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """
        Callback invoked for each BLE advertisement.

        Args:
            device: BLE device information
            advertisement_data: Advertisement data including service data and RSSI
        """
        # Only process advertisements from target device
        if device.address.upper() != self.target_mac:
            return

        timestamp = datetime.now().isoformat(timespec='milliseconds')
        rssi = advertisement_data.rssi or 0

        # Capture all service data
        service_data = {}
        if advertisement_data.service_data:
            for uuid, data in advertisement_data.service_data.items():
                service_data[str(uuid)] = data.hex()

        # Capture manufacturer data
        manufacturer_data = {}
        if advertisement_data.manufacturer_data:
            for company_id, data in advertisement_data.manufacturer_data.items():
                manufacturer_data[company_id] = data.hex()

        # Try to parse as BTHome from each service data
        parse_result = {"success": False}
        for uuid, hex_data in service_data.items():
            try:
                payload = bytes.fromhex(hex_data)
                measurements = parse_bthome(payload)
                parse_result = {
                    "success": True,
                    "service_uuid": uuid,
                    "measurements": measurements
                }
                break  # Found valid BTHome data
            except ValueError as e:
                parse_result = {
                    "success": False,
                    "error": str(e),
                    "service_uuid": uuid
                }

        # Store advertisement
        ad = Advertisement(
            timestamp=timestamp,
            rssi=rssi,
            service_data=service_data,
            manufacturer_data=manufacturer_data,
            parse_result=parse_result
        )
        self.advertisements.append(ad)

        # Display to console
        if not self.quiet:
            self._display_advertisement(ad)

    def _display_advertisement(self, ad: Advertisement):
        """
        Display advertisement to console in human-readable format.

        Args:
            ad: Advertisement to display
        """
        print(f"\n[{ad.timestamp}] RSSI: {ad.rssi} dBm")

        # Show service data
        if ad.service_data:
            for uuid, hex_data in ad.service_data.items():
                print(f"  Service UUID: {uuid}")
                print(f"    Data (hex): {hex_data}")

        # Show manufacturer data if present
        if ad.manufacturer_data:
            for company_id, hex_data in ad.manufacturer_data.items():
                print(f"  Manufacturer ID: {company_id}")
                print(f"    Data (hex): {hex_data}")

        # Show parse result
        if ad.parse_result["success"]:
            print(f"    BTHome parse: ✅ SUCCESS (from {ad.parse_result.get('service_uuid', 'unknown')})")
            measurements = ad.parse_result["measurements"]
            for key, value in measurements.items():
                if key == "temperature":
                    print(f"      - Temperature: {value}°C")
                elif key == "humidity":
                    print(f"      - Humidity: {value}%")
                elif key == "battery":
                    print(f"      - Battery: {value}%")
                else:
                    print(f"      - {key}: {value}")
        else:
            error = ad.parse_result.get("error", "Unknown error")
            print(f"    BTHome parse: ❌ FAILED - {error}")

    async def scan(self, duration: Optional[int] = None):
        """
        Start scanning for advertisements.

        Args:
            duration: Optional duration in seconds. If None, scan until interrupted.
        """
        print(f"Monitoring MAC: {self.target_mac}")
        if duration:
            print(f"Duration: {duration} seconds")
        else:
            print("Duration: Continuous (Ctrl+C to stop)")
        print("=" * 60)

        scanner = BleakScanner(detection_callback=self._detection_callback)

        try:
            await scanner.start()

            if duration:
                await asyncio.sleep(duration)
            else:
                # Run until interrupted
                while self.running:
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            if not self.quiet:
                print("\n\nScan interrupted by user")
        finally:
            await scanner.stop()

    def get_statistics(self) -> dict:
        """
        Calculate statistics from collected advertisements.

        Returns:
            Dictionary containing statistics
        """
        total = len(self.advertisements)
        if total == 0:
            return {
                "total_advertisements": 0,
                "parse_success_rate": 0.0,
                "average_rssi": 0.0,
                "service_uuids_seen": []
            }

        successful_parses = sum(1 for ad in self.advertisements if ad.parse_result["success"])
        success_rate = successful_parses / total

        average_rssi = sum(ad.rssi for ad in self.advertisements) / total

        # Collect all unique service UUIDs
        service_uuids = set()
        for ad in self.advertisements:
            service_uuids.update(ad.service_data.keys())

        return {
            "total_advertisements": total,
            "parse_success_rate": round(success_rate, 2),
            "successful_parses": successful_parses,
            "failed_parses": total - successful_parses,
            "average_rssi": round(average_rssi, 1),
            "service_uuids_seen": sorted(service_uuids)
        }

    def save_json(self, filename: Optional[str] = None) -> str:
        """
        Save captured advertisements to JSON file.

        Args:
            filename: Optional filename. If None, auto-generate with timestamp.

        Returns:
            Path to saved file
        """
        if filename is None:
            # Generate filename: ble_diagnostics_A4C138B63A7A_20251103_142315.json
            mac_sanitized = self.target_mac.replace(":", "")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ble_diagnostics_{mac_sanitized}_{timestamp}.json"

        data = {
            "mac_address": self.target_mac,
            "scan_start": self.advertisements[0].timestamp if self.advertisements else None,
            "scan_end": self.advertisements[-1].timestamp if self.advertisements else None,
            "advertisements": [asdict(ad) for ad in self.advertisements],
            "statistics": self.get_statistics()
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        return filename


def main():
    """Main entry point for diagnostic tool."""
    parser = argparse.ArgumentParser(
        description='BLE Sensor Diagnostic Tool - Monitor and analyze BLE advertisements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor for 30 seconds
  python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --duration 30

  # Continuous monitoring with JSON output
  python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --json

  # Custom JSON filename, quiet mode
  python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --json debug.json --quiet
        """
    )

    parser.add_argument(
        'mac_address',
        help='MAC address of BLE device to monitor (e.g., A4:C1:38:B6:36:7A)'
    )

    parser.add_argument(
        '--duration',
        type=int,
        metavar='SECONDS',
        help='Scan duration in seconds (default: continuous until Ctrl+C)'
    )

    parser.add_argument(
        '--json',
        nargs='?',
        const='',  # Flag present but no value
        metavar='FILENAME',
        help='Save results to JSON file (auto-generates filename if not provided)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress console output (useful with --json)'
    )

    args = parser.parse_args()

    # Create scanner
    scanner = DiagnosticScanner(args.mac_address, quiet=args.quiet)

    # Run scan
    try:
        asyncio.run(scanner.scan(duration=args.duration))
    except KeyboardInterrupt:
        pass

    # Display statistics
    if not args.quiet:
        print("\n" + "=" * 60)
        print("STATISTICS")
        print("=" * 60)
        stats = scanner.get_statistics()
        print(f"Total advertisements: {stats['total_advertisements']}")
        print(f"Successful parses: {stats['successful_parses']}")
        print(f"Failed parses: {stats['failed_parses']}")
        print(f"Parse success rate: {stats['parse_success_rate'] * 100:.1f}%")
        print(f"Average RSSI: {stats['average_rssi']} dBm")
        if stats['service_uuids_seen']:
            print(f"Service UUIDs seen:")
            for uuid in stats['service_uuids_seen']:
                print(f"  - {uuid}")

    # Save JSON if requested
    if args.json is not None:
        filename = args.json if args.json else None
        saved_path = scanner.save_json(filename)
        print(f"\nResults saved to: {saved_path}")


if __name__ == '__main__':
    main()
