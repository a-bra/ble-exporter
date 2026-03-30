# ABOUTME: Tests for the web dashboard endpoint showing latest sensor readings
# ABOUTME: Verifies HTML rendering, device display, auto-refresh, and data formatting
"""
Tests for the dashboard endpoint that displays latest sensor readings.
"""
import pytest
from aiohttp.test_utils import TestClient, TestServer

from ble_exporter.config import AppConfig
from ble_exporter.exporter import create_app, StatusTracker, READINGS_KEY


@pytest.fixture
def dashboard_config():
    """Create test configuration with two devices."""
    return AppConfig(
        scan_interval_seconds=30,
        scan_duration_seconds=5,
        listen_port=8000,
        devices={
            "A4:C1:38:11:22:33": "living_room",
            "A4:C1:38:44:55:66": "bedroom",
        },
        log_file="/tmp/test_dashboard.log"
    )


@pytest.fixture
def status_tracker():
    """Create a fresh StatusTracker."""
    return StatusTracker(
        scan_interval_seconds=30,
        scan_duration_seconds=5
    )


def make_app_with_readings(config, status_tracker, readings):
    """Helper to create app with pre-populated readings."""
    app = create_app(config, status_tracker)
    app[READINGS_KEY] = readings
    return app


@pytest.mark.asyncio
async def test_dashboard_returns_html(dashboard_config, status_tracker):
    """GET / should return 200 with text/html content type."""
    readings = {"living_room": None, "bedroom": None}
    app = make_app_with_readings(dashboard_config, status_tracker, readings)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/')
        assert resp.status == 200
        assert 'text/html' in resp.content_type


@pytest.mark.asyncio
async def test_dashboard_shows_device_names(dashboard_config, status_tracker):
    """Dashboard should display all configured device names."""
    readings = {"living_room": None, "bedroom": None}
    app = make_app_with_readings(dashboard_config, status_tracker, readings)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/')
        html = await resp.text()
        assert 'living_room' in html
        assert 'bedroom' in html


@pytest.mark.asyncio
async def test_dashboard_shows_readings(dashboard_config, status_tracker):
    """Dashboard should display temperature, humidity, battery, and timestamp."""
    readings = {
        "living_room": {
            "temperature": 21.5,
            "humidity": 65.3,
            "battery": 89.0,
            "last_seen": "2026-03-28 14:30:05",
        },
        "bedroom": {
            "temperature": 18.2,
            "humidity": 55.0,
            "battery": 72.0,
            "last_seen": "2026-03-28 14:30:05",
        },
    }
    app = make_app_with_readings(dashboard_config, status_tracker, readings)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/')
        html = await resp.text()
        assert '21.5' in html
        assert '65.3' in html
        assert '>89<' in html  # battery rendered as integer
        assert '18.2' in html
        assert '2026-03-28 14:30:05' in html


@pytest.mark.asyncio
async def test_dashboard_shows_never_for_unseen_devices(dashboard_config, status_tracker):
    """Devices that have never reported should show 'Never' and 'N/A'."""
    readings = {
        "living_room": {
            "temperature": 21.5,
            "humidity": 65.3,
            "battery": 89.0,
            "last_seen": "2026-03-28 14:30:05",
        },
        "bedroom": None,
    }
    app = make_app_with_readings(dashboard_config, status_tracker, readings)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/')
        html = await resp.text()
        assert 'Never' in html
        assert 'N/A' in html


@pytest.mark.asyncio
async def test_dashboard_has_auto_refresh(dashboard_config, status_tracker):
    """Dashboard should include a meta refresh tag set to 60 seconds."""
    readings = {"living_room": None, "bedroom": None}
    app = make_app_with_readings(dashboard_config, status_tracker, readings)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/')
        html = await resp.text()
        assert 'http-equiv="refresh"' in html
        assert 'content="60"' in html
        assert 'name="viewport"' in html
