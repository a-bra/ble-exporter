# ABOUTME: HTTP server for exposing metrics and health endpoints
# ABOUTME: Provides /healthz, /metrics, and /status endpoints via aiohttp
from dataclasses import dataclass
from typing import Optional
from aiohttp import web
import json

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ble_exporter.config import AppConfig


@dataclass
class StatusTracker:
    """Tracks scan status and metadata for /status endpoint."""
    scan_interval_seconds: int
    scan_duration_seconds: int
    last_scan_timestamp: int = 0
    devices_seen: int = 0

    def update(self, timestamp: int, num_devices: int) -> None:
        """Update scan status with latest scan results."""
        self.last_scan_timestamp = timestamp
        self.devices_seen = num_devices


# AppKey for type-safe access to config and status
CONFIG_KEY = web.AppKey('config', AppConfig)
STATUS_KEY = web.AppKey('status', StatusTracker)


async def healthz_handler(request: web.Request) -> web.Response:
    """
    Health check endpoint.

    Returns:
        200 OK with "ok" body
    """
    return web.Response(text="ok", status=200)


async def metrics_handler(request: web.Request) -> web.Response:
    """
    Prometheus metrics endpoint.

    Returns:
        200 OK with Prometheus metrics in text format
    """
    metrics_output = generate_latest()
    return web.Response(
        body=metrics_output,
        content_type='text/plain',
        charset='utf-8'
    )


async def status_handler(request: web.Request) -> web.Response:
    """
    Status endpoint returning scan metadata.

    Returns:
        200 OK with JSON containing scan status
    """
    status = request.app[STATUS_KEY]

    status_data = {
        "scan_interval_seconds": status.scan_interval_seconds,
        "scan_duration_seconds": status.scan_duration_seconds,
        "last_scan_timestamp": status.last_scan_timestamp,
        "devices_seen": status.devices_seen
    }

    return web.json_response(status_data)


def create_app(config: AppConfig, status_tracker: Optional[StatusTracker] = None) -> web.Application:
    """
    Create and configure aiohttp application.

    Args:
        config: Application configuration
        status_tracker: Optional StatusTracker for /status endpoint

    Returns:
        Configured aiohttp Application instance
    """
    app = web.Application()

    # Store config in app for access by handlers
    app[CONFIG_KEY] = config

    # Store status tracker if provided
    if status_tracker is None:
        # Create default tracker from config
        status_tracker = StatusTracker(
            scan_interval_seconds=config.scan_interval_seconds,
            scan_duration_seconds=config.scan_duration_seconds
        )
    app[STATUS_KEY] = status_tracker

    # Register routes
    app.router.add_get('/healthz', healthz_handler)
    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/status', status_handler)

    return app
