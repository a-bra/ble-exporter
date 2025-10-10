## 1  High-Level Blueprint

| Phase                 | Goal                                        | Key Outputs                           |
| --------------------- | ------------------------------------------- | ------------------------------------- |
| 0 — Bootstrap         | Local tooling & repo scaffolding            | Git repo, virtual-env, CI skeleton    |
| 1 — Core Library      | Parse config, log, parse BLE packets        | `config.py`, `logger.py`, `parser.py` |
| 2 — BLE I/O           | Non-blocking BLE scan abstraction           | `scanner.py` + interface mocks        |
| 3 — Metrics           | Prometheus registry & update logic          | `metrics.py`, metric unit tests       |
| 4 — HTTP Exporter     | `/metrics`, `/healthz`, `/status` endpoints | `exporter.py`                         |
| 5 — Service Loop      | Scheduler tying scanner → parser → metrics  | `main.py`                             |
| 6 — Packaging & Ops   | systemd unit, Dockerfile (optional)         | deploy artefacts                      |
| 7 — Integration & E2E | End-to-end test harness & docs              | CI passing green                      |

---

## 2  Iterative Milestones (build on each other)

1. **Scaffold & CI**
2. **Config Loader + Tests**
3. **Structured Logger + Tests**
4. **Packet Parser + Tests**
5. **BLE Scanner Stub + Tests**
6. **Prometheus Metric Registry + Tests**
7. **HTTP Server Skeleton (`/healthz`) + Tests**
8. **Metrics Endpoint Integration (`/metrics`)**
9. **Status Endpoint Integration (`/status`)**
10. **Scheduler Loop Wiring**
11. **Systemd Service & Logging Verification**
12. **Full End-to-End Validation**

Each milestone leaves the repo in a runnable, CI-green state.

---

## 3  Step-Level Decomposition (right-sized)

Below, every milestone is broken into 1-to-4 atomic steps. Each step:

* delivers a vertical slice (code **plus** tests)
* avoids cross-cutting refactors
* can be finished in < 1 h by a single engineer
* introduces at most one new external dependency

| #    | Milestone        | Step                                                                     | Description                                                                             |
| ---- | ---------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| 1-1  | Scaffold & CI    | Init repo                                                                | `git init`, MIT LICENSE, README, `.gitignore`, `ble_exporter/` package scaffolding      |
| 1-2  |                  | Poetry/requirements                                                      | Pin Python 3.10, add `bleak`, `prometheus_client`, `PyYAML`, `pytest`, `pytest-asyncio` |
| 1-3  |                  | Basic CI                                                                 | GitHub Actions workflow running `pytest` on push                                        |
| 2-1  | Config           | Implement `config.py`                                                    | YAML load + dataclass validation                                                        |
| 2-2  |                  | Unit tests                                                               | Fixtures for valid/invalid configs                                                      |
| 3-1  | Logger           | Implement `logger.py`                                                    | RotatingFileHandler at path from config                                                 |
| 3-2  |                  | Unit tests                                                               | Ensure file creation, log level filtering                                               |
| 4-1  | Parser           | Implement minimal BTHome decoder for temp/humidity/battery per spec      |                                                                                         |
| 4-2  |                  | Unit tests                                                               | Feed hex payloads → expected floats                                                     |
| 5-1  | Scanner          | Define `AbstractScanner` with async `scan()` returning raw adv packets   |                                                                                         |
| 5-2  |                  | MockScanner                                                              | Deterministic packet generator for tests/CI                                             |
| 5-3  |                  | Unit tests                                                               | Validate timeout behaviour, unknown device filtering                                    |
| 6-1  | Metrics          | Implement `metrics.py` with registry + helper to update gauges/counters  |                                                                                         |
| 6-2  |                  | Unit tests                                                               | Registry contains expected metric names/labels                                          |
| 7-1  | HTTP             | Tiny aiohttp server exposing `/healthz` returning **200/OK**             |                                                                                         |
| 7-2  |                  | Unit tests                                                               | aiohttp test-client ping                                                                |
| 8-1  | Metrics endpoint | Add `/metrics` using `prometheus_client`’s `generate_latest`             |                                                                                         |
| 8-2  |                  | Unit tests                                                               | Hit endpoint, scrape text, assert families present                                      |
| 9-1  | Status           | Implement `/status` JSON (scan stats)                                    |                                                                                         |
| 9-2  |                  | Unit tests                                                               | aiohttp test-client, JSON schema check                                                  |
| 10-1 | Scheduler        | Async task every `scan_interval_seconds` → scanner → parser → metrics    |                                                                                         |
| 10-2 |                  | Smoke test                                                               | Use `MockScanner`, run loop once, assert registry updated                               |
| 11-1 | Ops              | Write `ble_exporter.service` (systemd) & sample `config.yaml`            |                                                                                         |
| 11-2 |                  | Manual test                                                              | On Raspberry Pi, start service, check journal & `/healthz`                              |
| 12-1 | E2E              | End-to-end pytest that spins aiohttp server + MockScanner concurrently   |                                                                                         |
| 12-2 | Docs             | Update README with Prometheus scrape config                              |                                                                                         |

**Review**

* Steps are ≤ 150 LoC each (code + tests).
* Every external interface is mocked early so later work is safe.
* No step introduces BLE hardware dependency until milestone 11.

---

## 4  Prompts for a Code-Generation LLM

Copy-paste one prompt at a time. Each prompt is tagged as plain text.

### Prompt 1 – Repo Scaffold & CI ✅ COMPLETED

```text
You are ChatGPT-Dev, working in a clean Git repository.

TASK: Create project scaffolding for “ble_sensor_prometheus_exporter”.

REQUIREMENTS:
1. Python 3.10+ package named `ble_exporter`.
2. Subfolders/files:
   - ble_exporter/__init__.py  (empty)
   - tests/  (empty for now)
   - pyproject.toml managed by Poetry. Add runtime deps: bleak, prometheus_client, PyYAML. Add dev-deps: pytest, pytest-asyncio.
3. Add MIT LICENSE, README.md with project overview.
4. Add `.gitignore` for Python + Poetry + VS Code.
5. Add GitHub Actions workflow `.github/workflows/ci.yml` that runs `pytest` on Ubuntu latest, Python 3.10 & 3.11.

TDD: Add a placeholder test in `tests/test_sanity.py` that always passes to keep CI green.

OUTPUT: Modified files only (no commentary).
```

### Prompt 2 – Config Loader + Tests ✅ COMPLETED

```text
Context: Project scaffold exists. Implement milestone 2-1 and 2-2.

TASK: Add `ble_exporter/config.py` with:
* Dataclass `AppConfig`
* `load_config(path: str) -> AppConfig`
  - Validate mandatory keys: `scan_interval_seconds`, `scan_duration_seconds`, `listen_port`, `devices`
  - Provide defaults for `log_file` if missing
* Raise `ValueError` for bad YAML or missing keys.

TESTS: Create `tests/test_config.py` covering:
1. Successful load of sample config.
2. Missing key triggers `ValueError`.
3. Relative vs absolute log paths.

Keep existing tests passing.

OUTPUT: Code + tests only.
```

### Prompt 3 – Structured Logger ✅ COMPLETED

```text
TASK: Implement milestone 3-1 and 3-2.

CODE:
* Add `ble_exporter/logger.py` exposing `get_logger(app_config: AppConfig) -> logging.Logger`
  - RotatingFileHandler pointing to `app_config.log_file`
  - JSON-style formatter (`%(asctime)s %(levelname)s %(message)s`)
  - Default level INFO.

TESTS:
* `tests/test_logger.py`
  - Use tmp_path to verify log file is created and message is written.
  - Confirm only one handler attached.

Remember to import `AppConfig` from `config.py`.

Ensure all previous tests still pass.
```

### Prompt 4 – Packet Parser ✅ COMPLETED

```text
TASK: Implement BTHome parser (milestone 4-1 & 4-2).

CODE:
* File `ble_exporter/parser.py`
* Function `parse_bthome(payload: bytes) -> dict[str, float]`
  - Decode temperature (BLE object id 0x02, int16, factor 0.01)
  - Decode humidity  (id 0x03, uint16, factor 0.01)
  - Decode battery   (id 0x0A, uint8, factor 1)
  - Ignore other ids
* Raise `ValueError` on checksum failure or unknown format.

TESTS:
* `tests/test_parser.py`
  - Provide hex strings representing valid packets, assert float outputs within ±0.01 tolerance.
  - Invalid packet returns ValueError.

Keep code ≤ 100 LoC.
```

### Prompt 5 – BLE Scanner Stub & Tests ✅ COMPLETED

```text
TASK: Provide a scan abstraction usable without BLE hardware.

CODE:
* `ble_exporter/scanner.py`
  - `class AbstractScanner(Protocol): async def scan(duration_s: int) -> list[tuple[str, bytes]]`
  - `class BleakScannerImpl(AbstractScanner)` (placeholder, not yet implemented)
  - `class MockScanner(AbstractScanner)` configurable with list of (mac, payload) tuples to emit once per call.
* Export `get_scanner(use_mock: bool = False, data: list|None = None)`

TESTS:
* `tests/test_scanner.py`
  - Use `MockScanner` to simulate two devices; assert scan returns expected list.
  - Use `pytest.mark.asyncio`.

No BLE calls yet.
```

### Prompt 6 – Prometheus Metrics Module ✅ COMPLETED

```text
TASK: Add metrics registry (milestone 6-1 & 6-2).

CODE:
* `ble_exporter/metrics.py`
  - `from prometheus_client import Gauge`
  - Define Gauges per spec:
      ble_sensor_temperature_celsius{device}
      ble_sensor_humidity_percent{device}
      ble_sensor_battery_percent{device}
      ble_sensor_last_update_timestamp_seconds{device}
      ble_sensor_seen{device}
  - Provide `update_metrics(device_name: str, measurements: dict[str, float])`

TESTS:
* `tests/test_metrics.py`
  - Call `update_metrics` twice with different devices, use `registry.collect()` to assert metrics/labels exist and last values match.

All earlier tests stay green.
```

### Prompt 7 – HTTP Server Skeleton ✅ COMPLETED

```text
TASK: Implement aiohttp server (milestone 7-1 & 7-2).

CODE:
* `ble_exporter/exporter.py`
  - `create_app(config: AppConfig) -> web.Application`
  - Route `/healthz` returns 200/"ok".
  - Application stores reference to `AppConfig` in `app['config']`.

TESTS:
* `tests/test_exporter_healthz.py` using `aiohttp.test_utils.TestClient`.

No metrics yet.
```

### Prompt 8 – /metrics Endpoint Integration

```text
TASK: Extend exporter with Prometheus endpoint (milestone 8-1 & 8-2).

CODE:
* In `exporter.py`, add `/metrics` route returning `generate_latest()`.

TESTS:
* `tests/test_exporter_metrics.py`
  - Pre-populate one metric via `update_metrics`
  - GET /metrics and assert `ble_sensor_temperature_celsius` string appears.

Ensure healthz test still passes.
```

### Prompt 9 – /status Endpoint

```text
TASK: Add scan status endpoint (milestone 9-1 & 9-2).

* Extend `create_app` to accept a reference to a `StatusTracker` object holding:
    - scan_interval_seconds
    - scan_duration_seconds
    - last_scan_timestamp
    - devices_seen (int)
* Route `/status` returns JSON matching spec keys.

TESTS:
* `tests/test_exporter_status.py` verifying JSON keys/types.
```

### Prompt 10 – Scheduler Loop Wiring

```text
TASK: Wire everything together (milestone 10-1 & 10-2).

CODE:
* `ble_exporter/main.py`
  - Parse CLI arg `--config ./config.yaml`
  - Load config and logger.
  - Instantiate scanner (Mock/Bleak depending on flag)
  - Create aiohttp app with status tracker.
  - Start background task:
        while True:
            results = await scanner.scan(config.scan_duration_seconds)
            for mac,payload in results: 
                device_name = config.devices.get(mac)
                if device_name:
                    m = parse_bthome(payload)
                    update_metrics(device_name, m)
                    tracker.update(len(results))
            await asyncio.sleep(config.scan_interval_seconds - config.scan_duration_seconds)
  - Run `web._run_app(...)`

TESTS:
* `tests/test_main_loop.py`
  - Patch MockScanner producing one packet, run loop once with `asyncio.wait_for`, assert registry updated.

Keep CLI runnable: `python -m ble_exporter.main --config config.yaml`.
```

### Prompt 11 – Systemd & Ops

```text
TASK: Add deployment artefacts (milestone 11-1).

FILES:
* `contrib/ble_exporter.service`
  - [Unit] After=network.target
  - [Service] ExecStart=/usr/bin/python3 -m ble_exporter.main --config /etc/ble_exporter/config.yaml
              WorkingDirectory=/opt/ble_exporter
              Restart=on-failure
              User=ble
  - [Install] WantedBy=multi-user.target
* Sample `config.yaml` copied from spec.

Add doc section to README for installation.

No tests needed.
```

### Prompt 12 – End-to-End Test & Docs

```text
TASK: Final polish (milestone 12-1 & 12-2).

CODE:
* `tests/test_e2e.py`
  - Launch aiohttp app with MockScanner in a background task.
  - Poll `/metrics` until gauge appears, assert correctness.

DOCS:
* Expand README: architecture diagram ASCII, Prometheus scrape example, troubleshooting.

After this prompt all tests must pass and README must be fully updated.
```

---

