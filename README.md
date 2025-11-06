# BLE Sensor Prometheus Exporter

A Python application that passively listens for BLE advertisements from Xiaomi LYWSD03MMC thermometers/hygrometers (flashed with ATC_MiThermometer firmware using BTHome format) and exposes sensor data to Prometheus via an HTTP endpoint.

## Features

- **Passive BLE scanning** - No active connections to devices
- **Prometheus metrics** - Standard `/metrics` endpoint for scraping
- **Multiple endpoints** - `/healthz` for health checks, `/status` for scan metadata
- **Systemd integration** - Production-ready service management
- **Comprehensive logging** - File-based logging with rotation
- **Mock mode** - Test without BLE hardware

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BLE Exporter                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │   Scanner    │───▶│    Parser    │───▶│     Metrics     │   │
│  │  (BLE/Mock)  │    │   (BTHome)   │    │  (Prometheus)   │   │
│  └──────────────┘    └──────────────┘    └─────────────────┘   │
│         │                                          │             │
│         │                                          │             │
│         ▼                                          ▼             │
│  ┌──────────────┐                         ┌─────────────────┐   │
│  │    Logger    │                         │  HTTP Server    │   │
│  │  (rotating)  │                         │   (aiohttp)     │   │
│  └──────────────┘                         └─────────────────┘   │
│                                                   │              │
│                                            ┌──────┴──────┐       │
│                                            │             │       │
│                                            ▼             ▼       │
│                                      /metrics      /healthz      │
│                                      /status                     │
└─────────────────────────────────────────────────────────────────┘
        ▲                                           │
        │                                           │
   BLE Devices                              Prometheus Scraper
  (Thermometers)                              (HTTP Client)
```

### Data Flow

1. **Scanner** polls for BLE advertisements every N seconds
2. **Parser** decodes BTHome packets (temperature, humidity, battery)
3. **Metrics** updates Prometheus gauges with device labels
4. **HTTP Server** exposes metrics on `/metrics` for Prometheus
5. **Logger** records all scan events and errors to rotating log files
6. **Status Tracker** maintains scan metadata for `/status` endpoint

## Requirements

- Python 3.10+
- Raspberry Pi 4B (or any Linux system with Bluetooth)
- Ubuntu Server (or compatible Linux distribution)
- Xiaomi LYWSD03MMC sensors with ATC_MiThermometer firmware (BTHome format)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/ble_exporter.git
cd ble_exporter
```

### 2. Install dependencies

Using `uv` (recommended):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

Or using pip:

```bash
pip install -e .
```

### 3. Configure the application

Copy the example config and edit it with your device MAC addresses:

```bash
cp config.yaml.example config.yaml
nano config.yaml
```

Update the `devices` section with your BLE sensor MAC addresses:

```yaml
devices:
  "A4:C1:38:11:22:33": "living_room"
  "A4:C1:38:44:55:66": "bedroom"
```

### 4. Test the application

Run in mock mode (no BLE hardware required):

```bash
python -m ble_exporter.main --config config.yaml --mock-scanner
```

Or with real BLE scanning:

```bash
python -m ble_exporter.main --config config.yaml
```

Visit http://localhost:8000/healthz to verify it's running.

## Production Deployment

### 1. Create system user

```bash
sudo useradd --system --no-create-home --shell /bin/false ble
```

### 2. Install the application

```bash
sudo mkdir -p /opt/ble_exporter
sudo cp -r ble_exporter /opt/ble_exporter/
sudo mkdir -p /var/log/ble_exporter
sudo chown -R ble:ble /var/log/ble_exporter
```

### 3. Install configuration

```bash
sudo mkdir -p /etc/ble_exporter
sudo cp config.yaml /etc/ble_exporter/
sudo chown -R ble:ble /etc/ble_exporter
```

Update `/etc/ble_exporter/config.yaml` with:

```yaml
log_file: "/var/log/ble_exporter/ble_exporter.log"
```

### 4. Install systemd service

```bash
sudo cp contrib/ble_exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ble_exporter.service
sudo systemctl start ble_exporter.service
```

### 5. Verify service status

```bash
sudo systemctl status ble_exporter.service
sudo journalctl -u ble_exporter.service -f
```

## Prometheus Configuration

Add this scrape config to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'ble_sensors'
    static_configs:
      - targets: ['raspberrypi.local:8000']
        labels:
          instance: 'home'
```

Then reload Prometheus:

```bash
sudo systemctl reload prometheus
```

## API Endpoints

### GET /healthz

Health check endpoint.

**Response**: `200 OK` with plain text "ok"

### GET /metrics

Prometheus metrics endpoint.

**Response**: `200 OK` with Prometheus text format

**Metrics**:
- `ble_sensor_temperature_celsius{device="<name>"}` - Temperature in Celsius
- `ble_sensor_humidity_percent{device="<name>"}` - Relative humidity percentage
- `ble_sensor_battery_percent{device="<name>"}` - Battery level percentage
- `ble_sensor_last_update_timestamp_seconds{device="<name>"}` - Unix timestamp of last update
- `ble_sensor_seen{device="<name>"}` - Set to 1 for devices seen in latest scan

### GET /status

Scan metadata endpoint.

**Response**: `200 OK` with JSON

```json
{
  "scan_interval_seconds": 30,
  "scan_duration_seconds": 5,
  "last_scan_timestamp": 1716480000,
  "devices_seen": 2
}
```

## Development

### Running tests

```bash
uv run pytest -v
```

### Running with mock scanner

```bash
python -m ble_exporter.main --config config.yaml --mock-scanner
```

### Project structure

```
ble_exporter/
       __init__.py
       config.py          # YAML config parser
       logger.py          # File-based logging setup
       parser.py          # BTHome packet decoder
       scanner.py         # BLE scanning abstraction
       metrics.py         # Prometheus metrics registry
       exporter.py        # HTTP server (aiohttp)
       diagnostics.py     # Diagnostic tool for troubleshooting sensors
       main.py            # Application entrypoint
```

### Diagnostic Tool

The BLE diagnostic tool helps troubleshoot sensor advertisement issues by monitoring a specific MAC address and displaying all advertisement data in real-time.

**Basic usage:**

```bash
# Monitor a sensor for 30 seconds
python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --duration 30

# Continuous monitoring (Ctrl+C to stop)
python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A

# Save results to JSON with auto-generated filename
python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --json

# Save to custom JSON file, suppress console output
python -m ble_exporter.diagnostics A4:C1:38:B6:36:7A --json debug.json --quiet
```

**What it shows:**
- All BLE advertisement data (not just first service UUID)
- RSSI (signal strength) for each advertisement
- All service UUIDs and their hex data
- Manufacturer data (if present)
- BTHome parsing attempts with success/failure indicators
- Statistics summary: total ads, parse success rate, average RSSI

**Example output:**

```
[2025-11-03 14:23:15.123] RSSI: -45 dBm
  Service UUID: 0000181a-0000-1000-8000-00805f9b34fb
    Data (hex): 02 02 c8 09 03 84 19 0a 64
    BTHome parse: ✅ SUCCESS
      - Temperature: 25.04°C
      - Humidity: 64.52%
      - Battery: 100%

[2025-11-03 14:23:45.456] RSSI: -50 dBm
  Service UUID: 0000181a-0000-1000-8000-00805f9b34fb
    Data (hex): 40 00 68 0c 69 0b 10 00 11 01
    BTHome parse: ❌ FAILED - No valid sensor data found in packet
```

The JSON output file is named automatically with timestamp: `ble_diagnostics_A4C138B6367A_20251103_142315.json`

**Use cases:**
- Verify sensors are advertising in BTHome v2 format
- Debug parse errors by seeing raw advertisement data
- Check signal strength (RSSI) for placement issues
- Identify which service UUID contains BTHome data

## Troubleshooting

### BLE Permission Issues

If you get permission errors when scanning:

```bash
# Option 1: Add user to bluetooth group
sudo usermod -aG bluetooth $USER
# Then log out and back in

# Option 2: Grant CAP_NET_ADMIN capability
sudo setcap 'cap_net_admin+eip' $(which python3)
```

### Service Not Starting

Check logs:

```bash
sudo journalctl -u ble_exporter.service -n 50
```

Verify config file:

```bash
sudo cat /etc/ble_exporter/config.yaml
```

Check BLE adapter:

```bash
hciconfig
bluetoothctl list
```

### No Devices Found

1. Verify devices are advertising (check with `bluetoothctl scan on`)
2. Verify MAC addresses in config.yaml are correct
3. Check that devices have ATC_MiThermometer firmware with BTHome enabled
4. Verify scan_duration_seconds is long enough (at least 5 seconds)

## Credits

This project was built by:

- **Doctor Thighs** (Chief BLE Wrangler & Thigh Enthusiast) - Architecture, requirements, and keeping the build on track
- **BleBot McScanface** (AI Code Companion & Packet Parser Extraordinaire) - Implementation, testing, and documentation

Built with love, TDD, and an unreasonable amount of pytest fixtures. May your sensors always advertise and your Prometheus never go down. 🌡️📡

## License

MIT License - See LICENSE file for details

## Contributing

Pull requests welcome! Please ensure tests pass before submitting:

```bash
uv run pytest -v
```
