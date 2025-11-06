# ABOUTME: Main entry point for BLE sensor Prometheus exporter
# ABOUTME: Wires together scanner, parser, metrics, and HTTP server
import argparse
import asyncio
import time
from aiohttp import web

from ble_exporter.config import load_config
from ble_exporter.logger import get_logger
from ble_exporter.scanner import get_scanner
from ble_exporter.parser import parse_bthome
from ble_exporter.metrics import update_metrics
from ble_exporter.exporter import create_app, StatusTracker


def aggregate_scan_results(
    scan_results: list[tuple[str, bytes]],
    known_macs: set[str],
    logger
) -> dict[str, dict[str, float]]:
    """
    Aggregate measurements by MAC address within a scan period.

    Groups all packets by MAC address, parses each packet, and merges
    measurements. This handles sensors that alternate between sending
    temperature/humidity packets and battery packets.

    Args:
        scan_results: List of (mac_address, payload) tuples from scanner
        known_macs: Set of MAC addresses from config (for warning detection)
        logger: Logger instance for warnings

    Returns:
        Dictionary mapping MAC address to merged measurements:
        {"A4:C1:38:XX:XX:XX": {"temperature": 22.5, "battery": 85.0}}

    Behavior:
        - Silently skips unparseable packets
        - Last value wins for duplicate measurements
        - Warns if known MAC seen but ALL packets fail to parse
        - Unknown devices included in result (filtering happens in scan_loop)
    """
    # Group packets by MAC address
    packets_by_mac: dict[str, list[bytes]] = {}
    for mac, payload in scan_results:
        if mac not in known_macs:
            continue
        if mac not in packets_by_mac:
            packets_by_mac[mac] = []
        packets_by_mac[mac].append(payload)

    # Track which MACs we saw vs which successfully parsed
    seen_macs = set(packets_by_mac.keys())
    successful_macs = set()

    # Parse and merge measurements for each MAC
    aggregated: dict[str, dict[str, float]] = {}

    for mac, payloads in packets_by_mac.items():
        merged_measurements = {}

        for payload in payloads:
            try:
                measurements = parse_bthome(payload)
                # Merge measurements (last value wins for duplicates)
                merged_measurements.update(measurements)
            except ValueError:
                # Silently skip unparseable packets
                pass

        # Only include MAC if at least one packet parsed successfully
        if merged_measurements:
            aggregated[mac] = merged_measurements
            successful_macs.add(mac)

    # Warn if a known MAC was seen but all parses failed
    failed_known_macs = (seen_macs & known_macs) - successful_macs
    for mac in failed_known_macs:
        logger.warning(
            f"Device {mac} seen but all packets failed to parse. "
            f"Check sensor firmware or BTHome format compatibility."
        )

    return aggregated


async def scan_loop(scanner, config, status_tracker, logger):
    """
    Background task that continuously scans for BLE devices, aggregates packets,
    and updates metrics.

    Args:
        scanner: Scanner instance (MockScanner or BleakScannerImpl)
        config: Application configuration
        status_tracker: StatusTracker for updating scan metadata
        logger: Logger instance
    """
    while True:
        try:
            logger.info(f"Starting BLE scan for {config.scan_duration_seconds}s")
            results = await scanner.scan(config.scan_duration_seconds)

            # Aggregate measurements by MAC address (handles alternating packets)
            known_macs = set(config.devices.keys())
            aggregated = aggregate_scan_results(results, known_macs, logger)

            # Update metrics only for known devices
            devices_seen = 0
            for mac, measurements in aggregated.items():
                device_name = config.devices.get(mac)
                if device_name:
                    update_metrics(device_name, measurements)
                    devices_seen += 1
                    logger.info(f"Updated metrics for {device_name}: {measurements}")
                else:
                    logger.debug(f"Ignoring unknown device {mac}")

            # Update status tracker with current scan results
            timestamp = int(time.time())
            status_tracker.update(timestamp, devices_seen)

            logger.info(f"Scan complete: {devices_seen} devices updated")

            # Sleep until next scan
            sleep_duration = config.scan_interval_seconds - config.scan_duration_seconds
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                logger.warning(
                    f"scan_interval_seconds ({config.scan_interval_seconds}) "
                    f"is less than scan_duration_seconds ({config.scan_duration_seconds}). "
                    f"Running scans back-to-back."
                )

        except Exception as e:
            logger.error(f"Error in scan loop: {e}", exc_info=True)
            # Sleep briefly before retrying
            await asyncio.sleep(5)


async def start_background_tasks(app):
    """
    Startup handler that launches the background scan loop.

    Args:
        app: aiohttp Application instance
    """
    scanner = app['scanner']
    config = app['config']
    status_tracker = app['status_tracker']
    logger = app['logger']

    # Create and store the scan loop task
    app['scan_task'] = asyncio.create_task(
        scan_loop(scanner, config, status_tracker, logger)
    )


async def cleanup_background_tasks(app):
    """
    Cleanup handler that cancels the background scan loop.

    Args:
        app: aiohttp Application instance
    """
    app['scan_task'].cancel()
    try:
        await app['scan_task']
    except asyncio.CancelledError:
        pass  # Expected when cancelling the task


def main():
    """
    Main entry point. Parses CLI arguments, loads config, and starts the server.
    """
    parser = argparse.ArgumentParser(
        description='BLE Sensor Prometheus Exporter'
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to config YAML file'
    )
    parser.add_argument(
        '--mock-scanner',
        action='store_true',
        help='Use MockScanner instead of real BLE scanner (for testing)'
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Set up logger
    logger = get_logger(config)
    logger.info("Starting BLE Sensor Prometheus Exporter")
    logger.info(f"Config loaded from {args.config}")

    # Create scanner
    scanner = get_scanner(use_mock=args.mock_scanner)
    if args.mock_scanner:
        logger.info("Using MockScanner (no real BLE hardware)")
    else:
        logger.info("Using BleakScanner for real BLE devices")

    # Create status tracker
    status_tracker = StatusTracker(
        scan_interval_seconds=config.scan_interval_seconds,
        scan_duration_seconds=config.scan_duration_seconds
    )

    # Create aiohttp application
    app = create_app(config, status_tracker)

    # Store additional objects needed by background tasks
    app['scanner'] = scanner
    app['config'] = config
    app['status_tracker'] = status_tracker
    app['logger'] = logger

    # Register startup and cleanup handlers
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    # Run the web server
    logger.info(f"Starting HTTP server on port {config.listen_port}")
    web.run_app(app, host='0.0.0.0', port=config.listen_port)


if __name__ == '__main__':
    main()
