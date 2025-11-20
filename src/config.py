# Copyright (c) 2025. All rights reserved.
"""Configuration management for muc soundboard."""

import json
from pathlib import Path


class Config:
    """Manages application configuration."""

    def __init__(self) -> None:
        """Initialize the Config with default values and load existing config."""
        self.config_file = Path.home() / ".muc" / "config.json"
        self.sounds_dir = Path.cwd() / "sounds"
        self.output_device_id: int | None = None

        # Load existing config if it exists
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with self.config_file.open(encoding="utf-8") as f:
                    data = json.load(f)
                    self.output_device_id = data.get("output_device_id")
                    if "sounds_dir" in data:
                        self.sounds_dir = Path(data["sounds_dir"])
            except (json.JSONDecodeError, OSError):
                pass  # Use defaults

    def save(self) -> None:
        """Save configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "output_device_id": self.output_device_id,
            "sounds_dir": str(self.sounds_dir),
        }

        with self.config_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
