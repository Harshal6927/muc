# Copyright (c) 2025. All rights reserved.
# ruff: noqa: DOC201, DOC402
"""Shared pytest fixtures for MUC tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from rich.console import Console


@pytest.fixture
def console() -> Console:
    """Create a console that captures output for testing."""
    return Console(force_terminal=True, width=120, record=True)


@pytest.fixture
def temp_dir() -> Generator[Path]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """Create a temporary config file path."""
    config_dir = temp_dir / ".muc"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


@pytest.fixture
def sample_config_data() -> dict:
    """Sample configuration data for testing."""
    return {
        "output_device_id": 5,
        "sounds_dir": "/path/to/sounds",
        "volume": 0.75,
    }


@pytest.fixture
def temp_sounds_dir(temp_dir: Path) -> Path:
    """Create a temporary sounds directory with sample placeholder files."""
    sounds_dir = temp_dir / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)

    # Create empty placeholder files (actual audio not needed for scanning tests)
    (sounds_dir / "sound1.wav").touch()
    (sounds_dir / "sound2.mp3").touch()
    (sounds_dir / "sound3.ogg").touch()
    (sounds_dir / "subdir").mkdir()
    (sounds_dir / "subdir" / "sound4.flac").touch()

    return sounds_dir


@pytest.fixture
def mock_device_list() -> list[dict[str, int | str]]:
    """Mock device list for testing."""
    return [
        {"name": "Speakers (Realtek)", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "Microphone (Realtek)", "max_input_channels": 2, "max_output_channels": 0},
        {"name": "CABLE Input (VB-Audio Virtual Cable)", "max_input_channels": 0, "max_output_channels": 8},
        {"name": "CABLE Output (VB-Audio Virtual Cable)", "max_input_channels": 8, "max_output_channels": 0},
        {"name": "Headphones (USB Audio)", "max_input_channels": 0, "max_output_channels": 2},
    ]


@pytest.fixture
def mock_sounddevice(mock_device_list: list[dict[str, int | str]]) -> Generator[MagicMock]:
    """Mock sounddevice module for testing without audio hardware."""
    with patch("src.audio_manager.sd") as mock_sd:
        # Set up device query behavior
        def query_devices_handler(idx: int | None = None) -> Any:  # noqa: ANN401
            if idx is None:
                return mock_device_list
            if 0 <= idx < len(mock_device_list):
                return mock_device_list[idx]
            msg = f"Invalid device index: {idx}"
            raise ValueError(msg)

        mock_sd.query_devices = MagicMock(side_effect=query_devices_handler)
        mock_sd.play = MagicMock()
        mock_sd.stop = MagicMock()
        mock_sd.get_stream = MagicMock(return_value=None)

        yield mock_sd


@pytest.fixture
def mock_soundfile() -> Generator[MagicMock]:
    """Mock soundfile module for testing without actual audio files."""
    with patch("src.audio_manager.sf") as mock_sf:
        # Return stereo audio data by default (1 second at 44100Hz)
        rng = np.random.default_rng()
        mock_sf.read.return_value = (
            rng.random((44100, 2), dtype=np.float32),
            44100,
        )
        yield mock_sf


@pytest.fixture
def mock_pynput() -> Generator[MagicMock]:
    """Mock pynput keyboard module for testing hotkey listeners."""
    with patch("src.soundboard.keyboard") as mock_kb:
        mock_listener = MagicMock()
        mock_kb.GlobalHotKeys.return_value = mock_listener
        yield mock_kb


@pytest.fixture
def mock_audio_manager(console: Console) -> MagicMock:
    """Create a mock AudioManager for Soundboard tests."""
    mock_manager = MagicMock()
    mock_manager.console = console
    mock_manager.play_audio = MagicMock(return_value=True)
    mock_manager.stop_audio = MagicMock()
    mock_manager.output_device_id = 2
    mock_manager.volume = 1.0
    return mock_manager
