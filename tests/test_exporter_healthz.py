# ABOUTME: Unit tests for HTTP server health check endpoint
# ABOUTME: Tests /healthz endpoint using aiohttp test client
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ble_exporter.config import AppConfig
from ble_exporter.exporter import create_app, CONFIG_KEY


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
async def test_healthz_returns_200_ok(test_config):
    """Test that /healthz endpoint returns 200 OK."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/healthz')

        assert resp.status == 200
        text = await resp.text()
        assert text == "ok"


@pytest.mark.asyncio
async def test_healthz_response_content_type(test_config):
    """Test that /healthz returns plain text."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/healthz')

        assert resp.status == 200
        assert resp.content_type == 'text/plain'


@pytest.mark.asyncio
async def test_app_stores_config(test_config):
    """Test that application stores config in app."""
    app = create_app(test_config)

    assert CONFIG_KEY in app
    assert app[CONFIG_KEY] is test_config
    assert app[CONFIG_KEY].scan_interval_seconds == 30
    assert app[CONFIG_KEY].listen_port == 8000


@pytest.mark.asyncio
async def test_healthz_multiple_requests(test_config):
    """Test that /healthz can handle multiple requests."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        # Make multiple requests
        resp1 = await client.get('/healthz')
        resp2 = await client.get('/healthz')
        resp3 = await client.get('/healthz')

        assert resp1.status == 200
        assert resp2.status == 200
        assert resp3.status == 200


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(test_config):
    """Test that non-existent routes return 404."""
    app = create_app(test_config)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get('/nonexistent')

        assert resp.status == 404
