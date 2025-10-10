# ABOUTME: Configuration parser for BLE exporter application
# ABOUTME: Loads and validates YAML config with required BLE scanning parameters
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml


@dataclass
class AppConfig:
    """Application configuration loaded from YAML file."""
    scan_interval_seconds: int
    scan_duration_seconds: int
    listen_port: int
    devices: Dict[str, str]  # MAC address -> friendly name mapping
    log_file: str = "./logs/ble_exporter.log"


def load_config(path: str) -> AppConfig:
    """
    Load and validate application configuration from YAML file.

    Args:
        path: Path to YAML config file

    Returns:
        AppConfig instance with validated configuration

    Raises:
        ValueError: If config is invalid or missing required keys
    """
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ValueError(f"Config file not found: {path}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping")

    # Validate required keys
    required_keys = ['scan_interval_seconds', 'scan_duration_seconds', 'listen_port', 'devices']
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise ValueError(f"Missing required config keys: {', '.join(missing_keys)}")

    # Validate devices is a dict
    if not isinstance(data['devices'], dict):
        raise ValueError("'devices' must be a mapping of MAC addresses to names")

    # Provide default for log_file if missing
    log_file = data.get('log_file', './logs/ble_exporter.log')

    return AppConfig(
        scan_interval_seconds=data['scan_interval_seconds'],
        scan_duration_seconds=data['scan_duration_seconds'],
        listen_port=data['listen_port'],
        devices=data['devices'],
        log_file=log_file
    )
