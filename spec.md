# BLE Sensor Prometheus Exporter

## 📦 Project Title
**BLE Sensor Prometheus Exporter**

## 🧩 Purpose
A Python application that passively listens for BLE advertisements from a known set of Xiaomi LYWSD03MMC thermometers/hygrometers (flashed with ATC_MiThermometer firmware using the BTHome format) and exposes sensor data to Prometheus via an HTTP endpoint.

## 🛠️ Target Environment
- **Hardware**: Raspberry Pi 4B (4GB RAM)
- **OS**: Ubuntu Server Linux
- **Runtime**: Python 3.10+
- **BLE Interface**: Integrated Raspberry Pi Bluetooth
- **Execution**: As a systemd service

## 🗂️ Project Structure
```
ble_exporter/
├── __init__.py
├── config.py          # YAML config parser
├── scanner.py         # BLE scanning logic (using bleak)
├── parser.py          # BTHome packet parser
├── metrics.py         # Prometheus metric registration
├── exporter.py        # HTTP server with /metrics, /healthz, /status
├── logger.py          # File-only logger setup
├── utils.py           # Misc utilities
└── main.py            # Application entrypoint
logs/
└── ble_exporter.log   # Default log file path
config.yaml            # Configuration file
```

## 🧾 Configuration: `config.yaml`
```yaml
scan_interval_seconds: 30
scan_duration_seconds: 5
log_file: "./logs/ble_exporter.log"
listen_port: 8000
devices:
  "A4:C1:38:XX:XX:XX": "living_room"
  "A4:C1:38:YY:YY:YY": "bedroom"
```

## 📡 BLE Device Support
- **Device Model**: Xiaomi LYWSD03MMC
- **Firmware**: ATC_MiThermometer
- **Advertisement Format**: BTHome (unified, non-encrypted)

## 🔍 BLE Scanning Behavior
- Scan every **30 seconds**
- Each scan runs for **5 seconds**
- Only process devices listed in `config.yaml`
- Fail immediately on BLE adapter unavailability or scan errors

## 📊 Prometheus Metrics
**All metrics are prefixed with `ble_sensor_` and labeled with `device="<name>"`.**
- `ble_sensor_temperature_celsius`
- `ble_sensor_humidity_percent`
- `ble_sensor_battery_percent`
- `ble_sensor_last_update_timestamp_seconds` (Unix timestamp)
- `ble_sensor_seen` (constant value `1` per device seen per scan)

Only emit metrics from the **latest scan** — if a device is not seen, no metrics are exported for it.

## 🌐 HTTP Endpoints (Port `8000`)
- `/metrics` — Prometheus-compatible export
- `/healthz` — Returns `200 OK` if app is running
- `/status` — Returns JSON:
  ```json
  {
    "scan_interval_seconds": 30,
    "scan_duration_seconds": 5,
    "last_scan_timestamp": 1716480000,
    "devices_seen": 2
  }
  ```

All endpoints are **publicly accessible**, no authentication.

## 📁 Logging
- File-only logging (`./logs/ble_exporter.log`)
- Log BLE scan events, device detections, errors
- Log file path is configurable via `config.yaml`

## 🚨 Error Handling
- Exit with error if no BLE adapter is available at startup
- Exit and log on BLE scan failures
- Systemd should be used to auto-restart the service on failure

## 🧪 Testing Plan
- **Mockable scanner** interface for injecting synthetic BLE data
- **Unit tests** for:
  - Packet parsing (BTHome format)
  - Config loading and validation
  - Metric registration and update
  - HTTP endpoints (`/status`, `/metrics`)
- **Test mode** using randomly generated valid packets for offline CI/CD

## 🧰 Dependencies
- `bleak` (BLE scanning)
- `prometheus_client` (metrics endpoint)
- `PyYAML` (config parsing)
- `aiohttp` or `http.server` (for lightweight HTTP server)

## ✅ Implementation Summary
- Python package with CLI entrypoint (`main.py`)
- Reads config on startup
- Scans BLE every 30s, for 5s
- Parses BTHome packets from known devices
- Exports metrics and device info to Prometheus on `/metrics`
- Serves `/healthz` and `/status`
- Logs to file
- Tests with mocks + random packet generator
- Fails fast on BLE errors, managed by systemd
