# ABOUTME: HTTP server for exposing metrics and health endpoints
# ABOUTME: Provides /healthz, /metrics, and /status endpoints via aiohttp
from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ble_exporter.config import AppConfig

# AppKey for type-safe access to config
CONFIG_KEY = web.AppKey('config', AppConfig)


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


def create_app(config: AppConfig) -> web.Application:
    """
    Create and configure aiohttp application.

    Args:
        config: Application configuration

    Returns:
        Configured aiohttp Application instance
    """
    app = web.Application()

    # Store config in app for access by handlers
    app[CONFIG_KEY] = config

    # Register routes
    app.router.add_get('/healthz', healthz_handler)
    app.router.add_get('/metrics', metrics_handler)

    return app
