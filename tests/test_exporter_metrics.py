# ABOUTME: Unit tests for HTTP server metrics endpoint
# ABOUTME: Tests /metrics endpoint returns Prometheus-formatted metrics
import pytest
from aiohttp.test_utils import TestClient, TestServer

from ble_exporter.config import AppConfig
from ble_exporter.exporter import create_app
from ble_exporter.metrics import update_metrics


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
async def test_metrics_endpoint_returns_200(test_config):
    """Test that /metrics endpoint returns 200 OK."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/metrics')

        assert resp.status == 200


@pytest.mark.asyncio
async def test_metrics_endpoint_content_type(test_config):
    """Test that /metrics returns correct Prometheus content type."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/metrics')

        assert resp.status == 200
        # Prometheus content type should be text/plain with version info
        assert 'text/plain' in resp.content_type


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_populated_metric(test_config):
    """Test that populated metrics appear in /metrics output."""
    # Pre-populate a metric
    update_metrics("living_room", {
        'temperature': 21.5,
        'humidity': 65.4,
        'battery': 85.0
    })

    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/metrics')

        assert resp.status == 200
        text = await resp.text()

        # Verify metric names appear
        assert 'ble_sensor_temperature_celsius' in text
        assert 'ble_sensor_humidity_percent' in text
        assert 'ble_sensor_battery_percent' in text

        # Verify device label appears
        assert 'living_room' in text


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_metric_values(test_config):
    """Test that metric values appear correctly in output."""
    # Pre-populate metrics with specific values
    update_metrics("bedroom", {
        'temperature': 18.5,
        'humidity': 70.0
    })

    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/metrics')

        assert resp.status == 200
        text = await resp.text()

        # Check for device label
        assert 'bedroom' in text

        # Check for approximate values (Prometheus format may vary)
        assert '18.5' in text
        assert '70.0' in text


@pytest.mark.asyncio
async def test_metrics_endpoint_multiple_devices(test_config):
    """Test that multiple devices appear in metrics output."""
    # Populate metrics for multiple devices
    update_metrics("device1", {'temperature': 20.0})
    update_metrics("device2", {'temperature': 25.0})

    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/metrics')

        assert resp.status == 200
        text = await resp.text()

        # Both devices should appear
        assert 'device1' in text
        assert 'device2' in text


@pytest.mark.asyncio
async def test_metrics_endpoint_multiple_requests(test_config):
    """Test that /metrics can be called multiple times."""
    update_metrics("test", {'temperature': 22.0})

    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        # Make multiple requests
        resp1 = await client.get('/metrics')
        resp2 = await client.get('/metrics')
        resp3 = await client.get('/metrics')

        assert resp1.status == 200
        assert resp2.status == 200
        assert resp3.status == 200


@pytest.mark.asyncio
async def test_healthz_still_works_after_adding_metrics(test_config):
    """Test that /healthz still works after adding /metrics endpoint."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/healthz')

        assert resp.status == 200
        text = await resp.text()
        assert text == "ok"
