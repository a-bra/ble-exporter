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


async def scan_loop(scanner, config, status_tracker, logger):
    """
    Background task that continuously scans for BLE devices, parses packets,
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

            devices_seen = 0
            for mac, payload in results:
                device_name = config.devices.get(mac)
                if device_name:
                    try:
                        measurements = parse_bthome(payload)
                        update_metrics(device_name, measurements)
                        devices_seen += 1
                        logger.info(f"Updated metrics for {device_name}: {measurements}")
                    except ValueError as e:
                        logger.warning(f"Failed to parse packet from {mac}: {e}")
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
    await app['scan_task']


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
