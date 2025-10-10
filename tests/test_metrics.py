# ABOUTME: Unit tests for Prometheus metrics module
# ABOUTME: Tests metric registration, updates, and multi-device handling
import time
from pytest import approx
from prometheus_client import REGISTRY

from ble_exporter.metrics import (
    update_metrics,
    temperature_gauge,
    humidity_gauge,
    battery_gauge,
    last_update_gauge,
    seen_gauge
)


def test_update_metrics_with_all_measurements():
    """Test updating metrics with temperature, humidity, and battery."""
    device_name = "living_room"
    measurements = {
        'temperature': 21.5,
        'humidity': 65.4,
        'battery': 85.0
    }

    update_metrics(device_name, measurements)

    # Verify temperature
    temp_value = temperature_gauge.labels(device=device_name)._value.get()
    assert temp_value == approx(21.5, abs=0.01)

    # Verify humidity
    humidity_value = humidity_gauge.labels(device=device_name)._value.get()
    assert humidity_value == approx(65.4, abs=0.01)

    # Verify battery
    battery_value = battery_gauge.labels(device=device_name)._value.get()
    assert battery_value == approx(85.0, abs=0.01)

    # Verify seen is set to 1
    seen_value = seen_gauge.labels(device=device_name)._value.get()
    assert seen_value == 1.0

    # Verify last_update is recent (within last 2 seconds)
    last_update_value = last_update_gauge.labels(device=device_name)._value.get()
    assert abs(last_update_value - time.time()) < 2.0


def test_update_metrics_partial_measurements():
    """Test updating metrics with only some measurements."""
    device_name = "bedroom"
    measurements = {
        'temperature': 18.3
    }

    update_metrics(device_name, measurements)

    # Verify temperature is set
    temp_value = temperature_gauge.labels(device=device_name)._value.get()
    assert temp_value == approx(18.3, abs=0.01)

    # Verify seen and last_update are still set
    seen_value = seen_gauge.labels(device=device_name)._value.get()
    assert seen_value == 1.0

    last_update_value = last_update_gauge.labels(device=device_name)._value.get()
    assert abs(last_update_value - time.time()) < 2.0


def test_update_metrics_multiple_devices():
    """Test that metrics track multiple devices independently."""
    # Update device 1
    update_metrics("device1", {'temperature': 20.0, 'humidity': 50.0})

    # Update device 2
    update_metrics("device2", {'temperature': 25.0, 'humidity': 60.0})

    # Verify device1 metrics
    temp1 = temperature_gauge.labels(device="device1")._value.get()
    humidity1 = humidity_gauge.labels(device="device1")._value.get()
    assert temp1 == approx(20.0, abs=0.01)
    assert humidity1 == approx(50.0, abs=0.01)

    # Verify device2 metrics
    temp2 = temperature_gauge.labels(device="device2")._value.get()
    humidity2 = humidity_gauge.labels(device="device2")._value.get()
    assert temp2 == approx(25.0, abs=0.01)
    assert humidity2 == approx(60.0, abs=0.01)


def test_update_metrics_overwrites_previous_values():
    """Test that calling update_metrics multiple times overwrites previous values."""
    device_name = "kitchen"

    # First update
    update_metrics(device_name, {'temperature': 22.0})
    temp_value = temperature_gauge.labels(device=device_name)._value.get()
    assert temp_value == approx(22.0, abs=0.01)

    # Second update with different value
    update_metrics(device_name, {'temperature': 23.5})
    temp_value = temperature_gauge.labels(device=device_name)._value.get()
    assert temp_value == approx(23.5, abs=0.01)


def test_metrics_exist_in_registry():
    """Test that all metrics are registered in the Prometheus registry."""
    # Collect all metrics from registry
    metric_names = set()
    for metric in REGISTRY.collect():
        metric_names.add(metric.name)

    # Verify all our metrics exist
    assert 'ble_sensor_temperature_celsius' in metric_names
    assert 'ble_sensor_humidity_percent' in metric_names
    assert 'ble_sensor_battery_percent' in metric_names
    assert 'ble_sensor_last_update_timestamp_seconds' in metric_names
    assert 'ble_sensor_seen' in metric_names


def test_metrics_have_device_label():
    """Test that metrics have the correct device label."""
    device_name = "office"
    update_metrics(device_name, {'temperature': 19.5})

    # Collect metrics and verify labels
    found_metric = False
    for metric_family in REGISTRY.collect():
        if metric_family.name == 'ble_sensor_temperature_celsius':
            for sample in metric_family.samples:
                if sample.labels.get('device') == device_name:
                    found_metric = True
                    assert sample.value == approx(19.5, abs=0.01)

    assert found_metric, "Metric with device label not found in registry"


def test_update_metrics_with_negative_temperature():
    """Test updating metrics with negative temperature."""
    device_name = "freezer"
    measurements = {
        'temperature': -10.5,
        'humidity': 30.0
    }

    update_metrics(device_name, measurements)

    temp_value = temperature_gauge.labels(device=device_name)._value.get()
    assert temp_value == approx(-10.5, abs=0.01)


def test_update_metrics_with_zero_battery():
    """Test updating metrics with zero battery."""
    device_name = "low_battery_device"
    measurements = {
        'battery': 0.0
    }

    update_metrics(device_name, measurements)

    battery_value = battery_gauge.labels(device=device_name)._value.get()
    assert battery_value == 0.0


def test_update_metrics_empty_measurements():
    """Test updating metrics with empty measurements dict."""
    device_name = "empty_device"
    measurements = {}

    # Should not raise error, just update timestamp and seen
    update_metrics(device_name, measurements)

    seen_value = seen_gauge.labels(device=device_name)._value.get()
    assert seen_value == 1.0

    last_update_value = last_update_gauge.labels(device=device_name)._value.get()
    assert abs(last_update_value - time.time()) < 2.0
