# ABOUTME: HTTP server for exposing metrics, health endpoints, and sensor dashboard
# ABOUTME: Provides /, /healthz, /metrics, and /status endpoints via aiohttp
from dataclasses import dataclass
from typing import Optional
from aiohttp import web
import html
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


# AppKey for type-safe access to config, status, and readings
CONFIG_KEY = web.AppKey('config', AppConfig)
STATUS_KEY = web.AppKey('status', StatusTracker)
READINGS_KEY = web.AppKey('readings', dict)


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


async def dashboard_handler(request: web.Request) -> web.Response:
    """
    Dashboard endpoint showing latest sensor readings.

    Returns:
        200 OK with HTML table of device readings
    """
    readings = request.app[READINGS_KEY]

    rows = []
    for device_name, data in sorted(readings.items()):
        name = html.escape(device_name)
        if data is None:
            rows.append(
                f'<tr><td data-label="Device">{name}</td>'
                '<td data-label="Temp">N/A</td><td data-label="Humidity">N/A</td>'
                '<td data-label="Battery">N/A</td>'
                '<td data-label="Last Seen">Never</td></tr>'
            )
        else:
            temp = f"{data['temperature']:.1f}" if data.get('temperature') is not None else "N/A"
            hum = f"{data['humidity']:.1f}" if data.get('humidity') is not None else "N/A"
            bat = f"{data['battery']:.0f}" if data.get('battery') is not None else "N/A"
            last_seen = html.escape(data.get('last_seen', 'N/A'))
            rows.append(
                f'<tr><td data-label="Device">{name}</td>'
                f'<td data-label="Temp">{temp}</td><td data-label="Humidity">{hum}</td>'
                f'<td data-label="Battery">{bat}</td>'
                f'<td data-label="Last Seen">{last_seen}</td></tr>'
            )

    table_rows = "\n".join(rows)

    page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>BLE Sensors</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f5f5f5; }}
  h1 {{ color: #333; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 800px; background: #fff; }}
  th, td {{ padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #4a90d9; color: #fff; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #e9e9e9; }}
  @media (max-width: 600px) {{
    body {{ margin: 1rem; }}
    table, thead, tbody, tr, th, td {{ display: block; }}
    thead {{ display: none; }}
    tr {{ margin-bottom: 1rem; background: #fff; border-radius: 8px;
         box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 0.5rem 0; }}
    td {{ padding: 0.4rem 1rem; border-bottom: none;
         display: flex; justify-content: space-between; }}
    td::before {{ content: attr(data-label); font-weight: 600; color: #555; }}
    td:first-child {{ background: #4a90d9; color: #fff; border-radius: 8px 8px 0 0;
                      font-weight: 600; display: block; padding: 0.6rem 1rem; }}
    td:first-child::before {{ display: none; }}
  }}
</style>
</head>
<body>
<h1>BLE Sensors</h1>
<table>
<tr><th>Device</th><th>Temp (&deg;C)</th><th>Humidity (%)</th><th>Battery (%)</th><th>Last Seen</th></tr>
{table_rows}
</table>
</body>
</html>"""

    return web.Response(text=page, content_type='text/html')


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
    app.router.add_get('/', dashboard_handler)
    app.router.add_get('/healthz', healthz_handler)
    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/status', status_handler)

    return app
