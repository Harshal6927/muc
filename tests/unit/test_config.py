# Copyright (c) 2025. All rights reserved.
"""Unit tests for Config class."""

import json
from pathlib import Path
from unittest.mock import patch

from src.config import Config


class TestConfigInit:
    """Tests for Config initialization."""

    def test_default_values(self, temp_dir: Path) -> None:
        """Config should have sensible defaults when no config file exists."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id is None
            assert config.volume == 1.0
            assert config.sounds_dir == Path.cwd() / "sounds"

    def test_loads_existing_config(self, temp_dir: Path, sample_config_data: dict) -> None:
        """Config should load values from existing config file."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps(sample_config_data), encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id == sample_config_data["output_device_id"]
            assert config.volume == sample_config_data["volume"]
            assert config.sounds_dir == Path(sample_config_data["sounds_dir"])

    def test_uses_defaults_when_file_missing(self, temp_dir: Path) -> None:
        """Config should use defaults when config file doesn't exist."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id is None
            assert config.volume == 1.0


class TestConfigSave:
    """Tests for Config.save() method."""

    def test_creates_directory_if_missing(self, temp_dir: Path) -> None:
        """Save should create config directory if it doesn't exist."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()
            config.output_device_id = 5
            config.save()

            config_file = temp_dir / ".muc" / "config.json"
            assert config_file.exists()
            assert config_file.parent.exists()

    def test_saves_all_fields(self, temp_dir: Path) -> None:
        """Save should persist all configuration fields correctly."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()
            config.output_device_id = 10
            config.volume = 0.5
            custom_sounds = temp_dir / "custom" / "sounds"
            config.sounds_dir = custom_sounds
            config.save()

            config_file = temp_dir / ".muc" / "config.json"
            saved_data = json.loads(config_file.read_text(encoding="utf-8"))
            assert saved_data["output_device_id"] == 10
            assert saved_data["volume"] == 0.5
            assert saved_data["sounds_dir"] == str(custom_sounds)

    def test_overwrites_existing_config(self, temp_dir: Path, sample_config_data: dict) -> None:
        """Save should overwrite existing config file."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps(sample_config_data), encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()
            config.output_device_id = 99
            config.save()

            saved_data = json.loads(config_file.read_text(encoding="utf-8"))
            assert saved_data["output_device_id"] == 99


class TestConfigLoad:
    """Tests for Config.load() method."""

    def test_handles_corrupted_json(self, temp_dir: Path) -> None:
        """Load should handle corrupted JSON gracefully and use defaults."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text("{ invalid json syntax }", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            # Should use defaults without crashing
            assert config.output_device_id is None
            assert config.volume == 1.0

    def test_handles_empty_file(self, temp_dir: Path) -> None:
        """Load should handle empty config file gracefully."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text("", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id is None
            assert config.volume == 1.0

    def test_handles_missing_fields(self, temp_dir: Path) -> None:
        """Load should handle missing fields and use defaults for them."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text('{"output_device_id": 5}', encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id == 5
            assert config.volume == 1.0  # Default

    def test_handles_extra_fields(self, temp_dir: Path) -> None:
        """Load should ignore extra fields in config file."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        data = {
            "output_device_id": 3,
            "volume": 0.8,
            "sounds_dir": "/test/sounds",
            "unknown_field": "should be ignored",
        }
        config_file.write_text(json.dumps(data), encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id == 3
            assert config.volume == 0.8

    def test_handles_null_values(self, temp_dir: Path) -> None:
        """Load should handle null values in config file."""
        config_dir = temp_dir / ".muc"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        data = {
            "output_device_id": None,
            "volume": 0.5,
        }
        config_file.write_text(json.dumps(data), encoding="utf-8")

        with patch("pathlib.Path.home", return_value=temp_dir):
            config = Config()

            assert config.output_device_id is None
            assert config.volume == 0.5


class TestConfigRoundTrip:
    """Tests for save/load round-trip operations."""

    def test_round_trip_preserves_data(self, temp_dir: Path) -> None:
        """Saving and loading should preserve all data."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            # Create and save config
            config1 = Config()
            config1.output_device_id = 42
            config1.volume = 0.65
            config1.sounds_dir = Path("/my/sounds")
            config1.save()

            # Load into new instance
            config2 = Config()

            assert config2.output_device_id == 42
            assert config2.volume == 0.65
            assert config2.sounds_dir == Path("/my/sounds")
