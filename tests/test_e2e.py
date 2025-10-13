"""
End-to-end tests for the complete BLE exporter application.

These tests verify the full application flow: scanner → parser → metrics → HTTP endpoints.
"""
import asyncio
import time
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest import approx

from ble_exporter.config import AppConfig
from ble_exporter.scanner import MockScanner
from ble_exporter.exporter import create_app, StatusTracker
from ble_exporter.main import scan_loop, start_background_tasks, cleanup_background_tasks


@pytest.fixture
def e2e_config():
    """Create test configuration for E2E tests."""
    return AppConfig(
        scan_interval_seconds=1,  # Fast interval for testing
        scan_duration_seconds=1,
        listen_port=8000,
        devices={
            "A4:C1:38:11:22:33": "test_sensor_1",
            "A4:C1:38:44:55:66": "test_sensor_2",
        },
        log_file="/tmp/test_e2e.log"
    )


@pytest.fixture
def mock_logger():
    """Create a mock logger for E2E tests."""
    import logging
    logger = logging.getLogger("e2e_test")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.NullHandler()
        logger.addHandler(handler)
    return logger


@pytest.mark.asyncio
async def test_e2e_full_application_flow(e2e_config, mock_logger):
    """
    Test the complete application flow end-to-end.

    Verifies that:
    1. The application starts successfully
    2. The scan loop runs and updates metrics
    3. All HTTP endpoints work correctly
    4. Metrics contain expected sensor data
    """
    # Create test data - two sensors with valid BTHome packets
    test_payload_1 = bytes([
        0x02,  # BTHome v2
        0x02, 0x66, 0x08,  # Temperature: 21.5°C
        0x03, 0xBF, 0x28,  # Humidity: 104.31%
        0x0A, 0x55,        # Battery: 85%
    ])

    test_payload_2 = bytes([
        0x02,  # BTHome v2
        0x02, 0x00, 0x00,  # Temperature: 0°C
        0x03, 0x00, 0x00,  # Humidity: 0%
        0x0A, 0x64,        # Battery: 100%
    ])

    scanner = MockScanner(data=[
        ("A4:C1:38:11:22:33", test_payload_1),
        ("A4:C1:38:44:55:66", test_payload_2),
    ])

    # Create application
    status_tracker = StatusTracker(
        scan_interval_seconds=e2e_config.scan_interval_seconds,
        scan_duration_seconds=e2e_config.scan_duration_seconds
    )
    app = create_app(e2e_config, status_tracker)

    # Add scanner and other dependencies to app
    app['scanner'] = scanner
    app['config'] = e2e_config
    app['status_tracker'] = status_tracker
    app['logger'] = mock_logger

    # Start background tasks
    await start_background_tasks(app)

    # Give the scan loop time to run at least once
    await asyncio.sleep(0.5)

    # Create test client
    async with TestClient(TestServer(app)) as client:
        # Test /healthz endpoint
        resp = await client.get('/healthz')
        assert resp.status == 200
        text = await resp.text()
        assert text == 'ok'

        # Test /status endpoint
        resp = await client.get('/status')
        assert resp.status == 200
        status_data = await resp.json()
        assert status_data['devices_seen'] == 2
        assert status_data['scan_interval_seconds'] == 1
        assert status_data['scan_duration_seconds'] == 1
        assert status_data['last_scan_timestamp'] > 0

        # Test /metrics endpoint
        resp = await client.get('/metrics')
        assert resp.status == 200
        assert resp.content_type == 'text/plain'

        metrics_text = await resp.text()

        # Verify metrics for test_sensor_1
        assert 'ble_sensor_temperature_celsius{device="test_sensor_1"}' in metrics_text
        assert 'ble_sensor_humidity_percent{device="test_sensor_1"}' in metrics_text
        assert 'ble_sensor_battery_percent{device="test_sensor_1"}' in metrics_text
        assert 'ble_sensor_seen{device="test_sensor_1"}' in metrics_text

        # Verify metrics for test_sensor_2
        assert 'ble_sensor_temperature_celsius{device="test_sensor_2"}' in metrics_text
        assert 'ble_sensor_humidity_percent{device="test_sensor_2"}' in metrics_text
        assert 'ble_sensor_battery_percent{device="test_sensor_2"}' in metrics_text
        assert 'ble_sensor_seen{device="test_sensor_2"}' in metrics_text

    # Cleanup
    await cleanup_background_tasks(app)


@pytest.mark.asyncio
async def test_e2e_metrics_update_over_time(e2e_config, mock_logger):
    """
    Test that metrics update correctly over multiple scan cycles.
    """
    # First scan returns one device
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])  # 21.5°C

    scanner = MockScanner(data=[
        ("A4:C1:38:11:22:33", test_payload)
    ])

    status_tracker = StatusTracker(
        scan_interval_seconds=e2e_config.scan_interval_seconds,
        scan_duration_seconds=e2e_config.scan_duration_seconds
    )
    app = create_app(e2e_config, status_tracker)

    app['scanner'] = scanner
    app['config'] = e2e_config
    app['status_tracker'] = status_tracker
    app['logger'] = mock_logger

    await start_background_tasks(app)

    # Wait for first scan
    await asyncio.sleep(0.3)

    async with TestClient(TestServer(app)) as client:
        # Check first scan results
        resp = await client.get('/status')
        status1 = await resp.json()
        assert status1['devices_seen'] == 1

        # Wait for second scan
        await asyncio.sleep(1.2)

        # Check second scan results
        resp = await client.get('/status')
        status2 = await resp.json()
        assert status2['devices_seen'] == 1
        assert status2['last_scan_timestamp'] > status1['last_scan_timestamp']

    await cleanup_background_tasks(app)


@pytest.mark.asyncio
async def test_e2e_no_devices_seen(e2e_config, mock_logger):
    """
    Test E2E flow when no known devices are seen.
    """
    # Scanner returns empty results
    scanner = MockScanner(data=[])

    status_tracker = StatusTracker(
        scan_interval_seconds=e2e_config.scan_interval_seconds,
        scan_duration_seconds=e2e_config.scan_duration_seconds
    )
    app = create_app(e2e_config, status_tracker)

    app['scanner'] = scanner
    app['config'] = e2e_config
    app['status_tracker'] = status_tracker
    app['logger'] = mock_logger

    await start_background_tasks(app)
    await asyncio.sleep(0.3)

    async with TestClient(TestServer(app)) as client:
        # Health check should still work
        resp = await client.get('/healthz')
        assert resp.status == 200

        # Status should show 0 devices
        resp = await client.get('/status')
        status_data = await resp.json()
        assert status_data['devices_seen'] == 0
        assert status_data['last_scan_timestamp'] > 0

        # Metrics endpoint should still work
        resp = await client.get('/metrics')
        assert resp.status == 200

    await cleanup_background_tasks(app)


@pytest.mark.asyncio
async def test_e2e_unknown_device_ignored(e2e_config, mock_logger):
    """
    Test that unknown devices are ignored in the E2E flow.
    """
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])

    # Scanner returns an unknown device
    scanner = MockScanner(data=[
        ("FF:FF:FF:FF:FF:FF", test_payload)
    ])

    status_tracker = StatusTracker(
        scan_interval_seconds=e2e_config.scan_interval_seconds,
        scan_duration_seconds=e2e_config.scan_duration_seconds
    )
    app = create_app(e2e_config, status_tracker)

    app['scanner'] = scanner
    app['config'] = e2e_config
    app['status_tracker'] = status_tracker
    app['logger'] = mock_logger

    await start_background_tasks(app)
    await asyncio.sleep(0.3)

    async with TestClient(TestServer(app)) as client:
        # Status should show 0 devices (unknown device ignored)
        resp = await client.get('/status')
        status_data = await resp.json()
        assert status_data['devices_seen'] == 0

    await cleanup_background_tasks(app)


@pytest.mark.asyncio
async def test_e2e_concurrent_requests(e2e_config, mock_logger):
    """
    Test that the application handles concurrent requests correctly.
    """
    test_payload = bytes([0x02, 0x02, 0x66, 0x08])
    scanner = MockScanner(data=[("A4:C1:38:11:22:33", test_payload)])

    status_tracker = StatusTracker(
        scan_interval_seconds=e2e_config.scan_interval_seconds,
        scan_duration_seconds=e2e_config.scan_duration_seconds
    )
    app = create_app(e2e_config, status_tracker)

    app['scanner'] = scanner
    app['config'] = e2e_config
    app['status_tracker'] = status_tracker
    app['logger'] = mock_logger

    await start_background_tasks(app)
    await asyncio.sleep(0.3)

    async with TestClient(TestServer(app)) as client:
        # Make multiple concurrent requests
        tasks = [
            client.get('/healthz'),
            client.get('/status'),
            client.get('/metrics'),
            client.get('/healthz'),
            client.get('/status'),
        ]

        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        for resp in responses:
            assert resp.status == 200

    await cleanup_background_tasks(app)
