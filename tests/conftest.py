"""
Shared pytest fixtures and configuration for all test modules.
"""
import pytest
from ble_exporter.metrics import (
    temperature_gauge,
    humidity_gauge,
    battery_gauge,
    last_update_gauge,
    seen_gauge,
)


@pytest.fixture(autouse=True)
def clear_metrics():
    """Clear all Prometheus metric values before each test.

    This prevents test pollution where metrics from one test affect another.
    Prometheus metrics are global singletons, so we need to explicitly clear
    their internal _metrics dict between tests.
    """
    # Clear all metric label combinations before test
    for gauge in [temperature_gauge, humidity_gauge, battery_gauge, last_update_gauge, seen_gauge]:
        gauge._metrics.clear()

    yield  # Run the test

    # Clear all metric label combinations after test
    for gauge in [temperature_gauge, humidity_gauge, battery_gauge, last_update_gauge, seen_gauge]:
        gauge._metrics.clear()
