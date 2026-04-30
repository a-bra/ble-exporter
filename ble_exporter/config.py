# ABOUTME: Configuration parser for BLE exporter application
# ABOUTME: Loads and validates YAML config with required BLE scanning parameters
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class DeviceConfig:
    """Configuration for a single BLE device."""
    name: str
    bindkey: Optional[str] = None

    @property
    def encrypted(self) -> bool:
        return self.bindkey is not None


@dataclass
class AppConfig:
    """Application configuration loaded from YAML file."""
    scan_interval_seconds: int
    scan_duration_seconds: int
    listen_port: int
    devices: Dict[str, DeviceConfig]  # MAC address -> device config
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

    # Validate integer fields
    for key in ['scan_interval_seconds', 'scan_duration_seconds', 'listen_port']:
        if not isinstance(data[key], int):
            raise ValueError(f"'{key}' must be an integer, got {type(data[key]).__name__}")

    # Validate devices is a dict
    if not isinstance(data['devices'], dict):
        raise ValueError("'devices' must be a mapping of MAC addresses to names")

    # Normalize device entries into DeviceConfig instances
    devices: Dict[str, DeviceConfig] = {}
    for mac, value in data['devices'].items():
        if isinstance(value, str):
            devices[mac] = DeviceConfig(name=value)
        elif isinstance(value, dict):
            if 'name' not in value:
                raise ValueError(
                    f"Device '{mac}' dict entry missing 'name' key"
                )
            if 'bindkey' not in value:
                raise ValueError(
                    f"Device '{mac}' dict entry missing 'bindkey' key"
                )
            bindkey = str(value['bindkey'])
            if len(bindkey) != 32:
                raise ValueError(
                    f"Device '{mac}' bindkey must be 32 hex characters (16 bytes), "
                    f"got {len(bindkey)}"
                )
            try:
                bytes.fromhex(bindkey)
            except ValueError:
                raise ValueError(
                    f"Device '{mac}' bindkey must be valid hex, got '{bindkey}'"
                )
            devices[mac] = DeviceConfig(name=value['name'], bindkey=bindkey)
        else:
            raise ValueError(
                f"Device '{mac}' must be a string name or a dict with name/bindkey"
            )

    # Provide default for log_file if missing
    log_file = data.get('log_file', './logs/ble_exporter.log')

    return AppConfig(
        scan_interval_seconds=data['scan_interval_seconds'],
        scan_duration_seconds=data['scan_duration_seconds'],
        listen_port=data['listen_port'],
        devices=devices,
        log_file=log_file
    )
