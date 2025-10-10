# ABOUTME: Unit tests for configuration loading and validation
# ABOUTME: Tests YAML parsing, required key validation, and default value handling
import pytest
from pathlib import Path

from ble_exporter.config import load_config, AppConfig


def test_load_valid_config(tmp_path):
    """Test successful loading of a valid configuration file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
scan_duration_seconds: 5
log_file: "./logs/ble_exporter.log"
listen_port: 8000
devices:
  "A4:C1:38:11:22:33": "living_room"
  "A4:C1:38:44:55:66": "bedroom"
""")

    config = load_config(str(config_file))

    assert config.scan_interval_seconds == 30
    assert config.scan_duration_seconds == 5
    assert config.listen_port == 8000
    assert config.log_file == "./logs/ble_exporter.log"
    assert config.devices == {
        "A4:C1:38:11:22:33": "living_room",
        "A4:C1:38:44:55:66": "bedroom"
    }


def test_load_config_with_default_log_file(tmp_path):
    """Test that log_file gets default value when not specified."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
scan_duration_seconds: 5
listen_port: 8000
devices:
  "A4:C1:38:11:22:33": "living_room"
""")

    config = load_config(str(config_file))

    assert config.log_file == "./logs/ble_exporter.log"


def test_missing_required_key_raises_error(tmp_path):
    """Test that missing required keys trigger ValueError."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
listen_port: 8000
devices:
  "A4:C1:38:11:22:33": "living_room"
""")

    with pytest.raises(ValueError, match="Missing required config keys.*scan_duration_seconds"):
        load_config(str(config_file))


def test_missing_multiple_keys_raises_error(tmp_path):
    """Test that multiple missing keys are reported."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
""")

    with pytest.raises(ValueError, match="Missing required config keys"):
        load_config(str(config_file))


def test_invalid_yaml_raises_error(tmp_path):
    """Test that invalid YAML syntax raises ValueError."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
    invalid: yaml: syntax: here
    [broken
    """)

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(str(config_file))


def test_nonexistent_file_raises_error(tmp_path):
    """Test that missing config file raises ValueError."""
    nonexistent = tmp_path / "doesnotexist.yaml"

    with pytest.raises(ValueError, match="Config file not found"):
        load_config(str(nonexistent))


def test_relative_log_path(tmp_path):
    """Test config with relative log file path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
scan_duration_seconds: 5
listen_port: 8000
log_file: "./logs/app.log"
devices:
  "A4:C1:38:11:22:33": "living_room"
""")

    config = load_config(str(config_file))
    assert config.log_file == "./logs/app.log"


def test_absolute_log_path(tmp_path):
    """Test config with absolute log file path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
scan_duration_seconds: 5
listen_port: 8000
log_file: "/var/log/ble_exporter.log"
devices:
  "A4:C1:38:11:22:33": "living_room"
""")

    config = load_config(str(config_file))
    assert config.log_file == "/var/log/ble_exporter.log"


def test_devices_must_be_dict(tmp_path):
    """Test that devices must be a dictionary mapping."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scan_interval_seconds: 30
scan_duration_seconds: 5
listen_port: 8000
devices:
  - "A4:C1:38:11:22:33"
  - "A4:C1:38:44:55:66"
""")

    with pytest.raises(ValueError, match="'devices' must be a mapping"):
        load_config(str(config_file))
