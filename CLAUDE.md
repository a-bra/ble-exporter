# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BLE Sensor Prometheus Exporter - A Python application that passively listens for BLE advertisements from Xiaomi LYWSD03MMC thermometers/hygrometers (flashed with ATC_MiThermometer firmware using BTHome format) and exposes sensor data to Prometheus via an HTTP endpoint.

**Target deployment**: Raspberry Pi 4B running Ubuntu Server as a systemd service.

## Development Commands

### Environment Setup
```bash
uv sync                    # Install dependencies
```

### Running the Application
```bash
python -m ble_exporter.main --config config.yaml
```

### Testing
```bash
pytest                     # Run all tests
pytest tests/test_config.py  # Run specific test file
pytest -v                  # Verbose output
pytest -k "test_name"      # Run specific test by name
```

## Architecture

The project follows a layered architecture with clear separation of concerns:

### Core Components
- **config.py**: YAML config parser with dataclass validation. Single source of truth for application configuration.
- **logger.py**: File-only logging setup using RotatingFileHandler. No stdout logging - logs to file path specified in config.
- **scanner.py**: BLE scanning abstraction with `AbstractScanner` protocol. `BleakScannerImpl` for hardware, `MockScanner` for testing/CI. Returns list of `(mac_address, payload_bytes)` tuples.
- **parser.py**: BTHome packet decoder. Extracts temperature (0x02), humidity (0x03), battery (0x0A) from binary advertisement payloads.
- **metrics.py**: Prometheus metric registration and update logic. All metrics prefixed with `ble_sensor_` and labeled with `device="<name>"`.
- **exporter.py**: aiohttp HTTP server with three endpoints: `/metrics` (Prometheus scrape), `/healthz` (200 OK), `/status` (JSON with scan stats).
- **main.py**: Application entrypoint. Wires together: config load → scanner → parser → metrics update loop → HTTP server.

### Data Flow
1. Scanner runs every `scan_interval_seconds` for `scan_duration_seconds`
2. Raw BLE advertisements filtered to known devices (from config.yaml `devices` map)
3. BTHome packets parsed into temperature/humidity/battery values
4. Prometheus metrics updated with device name labels
5. HTTP `/metrics` endpoint serves latest values to Prometheus scraper

### Key Design Decisions
- **Only emit metrics from latest scan**: If a device is not seen in current scan, no metrics exported for it
- **Fail fast on BLE errors**: Application exits on adapter unavailability or scan failures. Systemd handles restart.
- **No mock mode**: Always use real scanner (or explicit MockScanner for tests). Never implement fake/stub behavior in production code paths.
- **Async-first**: All I/O operations use asyncio (BLE scanning, HTTP server, scheduler loop)

## Testing Strategy

### Test Isolation
- Use `MockScanner` for all tests requiring BLE functionality
- Tests should never touch real BLE hardware
- Use `pytest.mark.asyncio` for async test functions
- Use `tmp_path` fixture for file operations (logs, configs)

### Test Coverage Requirements
- **Unit tests**: Every module (config, logger, parser, scanner, metrics, exporter endpoints)
- **Integration tests**: Scheduler loop with MockScanner
- **End-to-end tests**: Full application with aiohttp test client + MockScanner

### Running Tests in CI
GitHub Actions workflow runs pytest on Ubuntu with Python 3.10 & 3.11. All tests must pass before merge.

## Configuration Format

`config.yaml` structure:
```yaml
scan_interval_seconds: 30      # Time between scan starts
scan_duration_seconds: 5       # How long each scan runs
log_file: "./logs/ble_exporter.log"
listen_port: 8000
devices:
  "A4:C1:38:XX:XX:XX": "living_room"  # MAC -> friendly name mapping
```

## Dependencies

- **bleak**: BLE scanning on Linux/Windows/macOS
- **prometheus_client**: Metric registry and `/metrics` endpoint generation
- **PyYAML**: Config file parsing
- **aiohttp**: Async HTTP server for endpoints
- **pytest + pytest-asyncio**: Testing framework

## Deployment

Systemd service file at `contrib/ble_exporter.service`. Service runs as unprivileged `ble` user with `Restart=on-failure`. Config lives at `/etc/ble_exporter/config.yaml`.

## Common Pitfalls

- **BTHome packet format**: Multi-byte values are little-endian. Temperature/humidity use 0.01 scaling factor.
- **BLE permissions**: On Linux, user needs `CAP_NET_ADMIN` or be in `bluetooth` group to scan without root.
- **Scan timing**: `scan_interval_seconds` is from start of one scan to start of next. Actual sleep time is `interval - duration`.
- **Metric staleness**: Prometheus expects metrics to persist between scrapes. We intentionally only export devices seen in latest scan - this is correct behavior to detect offline sensors.
