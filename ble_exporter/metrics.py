# ABOUTME: Prometheus metrics registry for BLE sensor data
# ABOUTME: Defines gauges for temperature, humidity, battery, and tracking metadata
import time
from prometheus_client import Gauge


# Define Prometheus Gauges with device label
temperature_gauge = Gauge(
    'ble_sensor_temperature_celsius',
    'Temperature reading in Celsius',
    ['device']
)

humidity_gauge = Gauge(
    'ble_sensor_humidity_percent',
    'Relative humidity reading in percent',
    ['device']
)

battery_gauge = Gauge(
    'ble_sensor_battery_percent',
    'Battery level in percent',
    ['device']
)

last_update_gauge = Gauge(
    'ble_sensor_last_update_timestamp_seconds',
    'Unix timestamp of last sensor update',
    ['device']
)

seen_gauge = Gauge(
    'ble_sensor_seen',
    'Constant value 1 indicating device was seen in latest scan',
    ['device']
)


def update_metrics(device_name: str, measurements: dict[str, float]) -> None:
    """
    Update Prometheus metrics for a specific device.

    Args:
        device_name: Friendly name of the device (used as 'device' label)
        measurements: Dictionary with sensor readings. Supported keys:
            - 'temperature': Temperature in Celsius
            - 'humidity': Humidity in percent
            - 'battery': Battery level in percent
    """
    # Update sensor readings if present
    if 'temperature' in measurements:
        temperature_gauge.labels(device=device_name).set(measurements['temperature'])

    if 'humidity' in measurements:
        humidity_gauge.labels(device=device_name).set(measurements['humidity'])

    if 'battery' in measurements:
        battery_gauge.labels(device=device_name).set(measurements['battery'])

    # Always update timestamp and seen indicator
    last_update_gauge.labels(device=device_name).set(time.time())
    seen_gauge.labels(device=device_name).set(1)
