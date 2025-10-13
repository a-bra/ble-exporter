# ABOUTME: Unit tests for HTTP server status endpoint
# ABOUTME: Tests /status endpoint returns scan metadata as JSON
import pytest
import json
from aiohttp.test_utils import TestClient, TestServer

from ble_exporter.config import AppConfig
from ble_exporter.exporter import create_app, StatusTracker


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={"AA:BB:CC:DD:EE:FF": "test_device"},
        log_file="./logs/test.log"
    )


@pytest.mark.asyncio
async def test_status_endpoint_returns_200(test_config):
    """Test that /status endpoint returns 200 OK."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')

        assert resp.status == 200


@pytest.mark.asyncio
async def test_status_endpoint_returns_json(test_config):
    """Test that /status returns JSON content type."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')

        assert resp.status == 200
        assert resp.content_type == 'application/json'


@pytest.mark.asyncio
async def test_status_endpoint_has_required_keys(test_config):
    """Test that /status returns all required JSON keys."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert 'scan_interval_seconds' in data
        assert 'scan_duration_seconds' in data
        assert 'last_scan_timestamp' in data
        assert 'devices_seen' in data


@pytest.mark.asyncio
async def test_status_endpoint_values_from_config(test_config):
    """Test that /status returns values from config."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert data['scan_interval_seconds'] == 30
        assert data['scan_duration_seconds'] == 5


@pytest.mark.asyncio
async def test_status_endpoint_default_values(test_config):
    """Test that /status returns default values for scan metadata."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert data['last_scan_timestamp'] == 0
        assert data['devices_seen'] == 0


@pytest.mark.asyncio
async def test_status_endpoint_with_custom_tracker(test_config):
    """Test that /status uses custom StatusTracker if provided."""
    tracker = StatusTracker(
        scan_interval_seconds=60,
        scan_duration_seconds=10,
        last_scan_timestamp=1716480000,
        devices_seen=3
    )

    app = create_app(test_config, status_tracker=tracker)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert data['scan_interval_seconds'] == 60
        assert data['scan_duration_seconds'] == 10
        assert data['last_scan_timestamp'] == 1716480000
        assert data['devices_seen'] == 3


@pytest.mark.asyncio
async def test_status_tracker_update_method(test_config):
    """Test that StatusTracker.update() modifies values."""
    tracker = StatusTracker(
        scan_interval_seconds=30,
        scan_duration_seconds=5
    )

    app = create_app(test_config, status_tracker=tracker)

    # Update tracker
    tracker.update(timestamp=1234567890, num_devices=2)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert data['last_scan_timestamp'] == 1234567890
        assert data['devices_seen'] == 2


@pytest.mark.asyncio
async def test_status_endpoint_value_types(test_config):
    """Test that /status returns correct value types."""
    tracker = StatusTracker(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        last_scan_timestamp=1716480000,
        devices_seen=2
    )

    app = create_app(test_config, status_tracker=tracker)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/status')
        data = await resp.json()

        assert isinstance(data['scan_interval_seconds'], int)
        assert isinstance(data['scan_duration_seconds'], int)
        assert isinstance(data['last_scan_timestamp'], int)
        assert isinstance(data['devices_seen'], int)
