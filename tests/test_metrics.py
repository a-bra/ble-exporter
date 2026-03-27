# ABOUTME: Unit tests for Prometheus metrics module
# ABOUTME: Tests metric registration, updates, and multi-device handling
import time
from pytest import approx
from prometheus_client import REGISTRY

from ble_exporter.metrics import (
    update_metrics,
    clear_device_metrics,
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


def test_clear_device_metrics_removes_sensor_values():
    """Test that clearing a device removes its sensor metrics from registry output."""
    device_name = "clear_test_device"

    # First set all metrics
    update_metrics(device_name, {
        'temperature': 22.0,
        'humidity': 55.0,
        'battery': 90.0,
    })

    # Verify metrics exist in registry
    registry_output = set()
    for metric_family in REGISTRY.collect():
        for sample in metric_family.samples:
            if sample.labels.get('device') == device_name:
                registry_output.add(metric_family.name)

    assert 'ble_sensor_temperature_celsius' in registry_output
    assert 'ble_sensor_humidity_percent' in registry_output
    assert 'ble_sensor_battery_percent' in registry_output
    assert 'ble_sensor_last_update_timestamp_seconds' in registry_output

    # Clear the device metrics
    clear_device_metrics(device_name)

    # Verify sensor metrics are gone from registry output
    remaining_metrics = set()
    for metric_family in REGISTRY.collect():
        for sample in metric_family.samples:
            if sample.labels.get('device') == device_name:
                remaining_metrics.add(metric_family.name)

    assert 'ble_sensor_temperature_celsius' not in remaining_metrics
    assert 'ble_sensor_humidity_percent' not in remaining_metrics
    assert 'ble_sensor_battery_percent' not in remaining_metrics
    assert 'ble_sensor_last_update_timestamp_seconds' not in remaining_metrics


def test_clear_device_metrics_sets_seen_to_zero():
    """Test that clearing a device sets its seen gauge to 0."""
    device_name = "seen_test_device"

    # Set the device as seen
    update_metrics(device_name, {'temperature': 20.0})
    assert seen_gauge.labels(device=device_name)._value.get() == 1.0

    # Clear the device
    clear_device_metrics(device_name)

    # seen_gauge should be 0, and still present in registry
    assert seen_gauge.labels(device=device_name)._value.get() == 0.0

    # Verify seen_gauge IS still in registry output (as presence indicator)
    found_seen = False
    for metric_family in REGISTRY.collect():
        if metric_family.name == 'ble_sensor_seen':
            for sample in metric_family.samples:
                if sample.labels.get('device') == device_name:
                    found_seen = True
                    assert sample.value == 0.0
    assert found_seen, "seen_gauge should still be visible in registry after clear"


def test_clear_device_metrics_handles_never_seen_device():
    """Test that clearing a device that was never seen does not raise an error."""
    # This should not raise any exception
    clear_device_metrics("never_existed_device")

    # Verify seen_gauge was set to 0 for this device
    seen_value = seen_gauge.labels(device="never_existed_device")._value.get()
    assert seen_value == 0.0
