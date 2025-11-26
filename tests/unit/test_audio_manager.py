# Copyright (c) 2025. All rights reserved.
"""Unit tests for AudioManager class."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from rich.console import Console

from src.audio_manager import AudioManager


class TestAudioManagerDevices:
    """Tests for device listing and management."""

    def test_list_devices_returns_all_devices(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should return list of all audio devices."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            devices = manager.list_devices()

            assert len(devices) == 5
            assert devices[0]["name"] == "Speakers (Realtek)"  # pyright: ignore[reportArgumentType]

    def test_find_virtual_cable_found(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should find VB-Cable device when present."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            cable_id = manager.find_virtual_cable()

            # CABLE Input (VB-Audio) is at index 2
            assert cable_id == 2

    def test_find_virtual_cable_not_found(self, console: Console) -> None:
        """Should return None when no virtual cable exists."""
        # Device list without virtual cables
        non_virtual_devices = [
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
            {"name": "Microphone", "max_input_channels": 2, "max_output_channels": 0},
        ]

        with patch("src.audio_manager.sd") as mock_sd:
            mock_sd.query_devices.return_value = non_virtual_devices
            mock_sd.query_devices.side_effect = lambda idx=None: (
                non_virtual_devices if idx is None else non_virtual_devices[idx]
            )

            manager = AudioManager(console)
            cable_id = manager.find_virtual_cable()

            assert cable_id is None

    def test_find_virtual_cable_detects_voicemeeter(self, console: Console) -> None:
        """Should detect Voicemeeter as virtual cable."""
        voicemeeter_devices = [
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
            {"name": "VoiceMeeter Input", "max_input_channels": 0, "max_output_channels": 8},
        ]

        with patch("src.audio_manager.sd") as mock_sd:
            mock_sd.query_devices.return_value = voicemeeter_devices
            mock_sd.query_devices.side_effect = lambda idx=None: (
                voicemeeter_devices if idx is None else voicemeeter_devices[idx]
            )

            manager = AudioManager(console)
            cable_id = manager.find_virtual_cable()

            assert cable_id == 1


class TestAudioManagerSetOutputDevice:
    """Tests for set_output_device method."""

    def test_set_output_device_valid(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should set valid output device successfully."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            result = manager.set_output_device(0)

            assert result is True
            assert manager.output_device_id == 0

    def test_set_output_device_no_output_channels(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should reject device with no output channels."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            # Device 1 is Microphone (input only)
            result = manager.set_output_device(1)

            assert result is False
            assert manager.output_device_id is None

    def test_set_output_device_invalid_id(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should reject invalid device ID."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            result = manager.set_output_device(999)

            assert result is False
            assert manager.output_device_id is None

    def test_set_output_device_negative_id(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should reject negative device ID."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            result = manager.set_output_device(-1)

            assert result is False
            assert manager.output_device_id is None


class TestAudioManagerVolume:
    """Tests for volume control."""

    def test_set_volume_valid_range(self, console: Console) -> None:
        """Should set volume within valid range."""
        manager = AudioManager(console)

        manager.set_volume(0.5)
        assert manager.volume == 0.5

        manager.set_volume(0.0)
        assert manager.volume == 0.0

        manager.set_volume(1.0)
        assert manager.volume == 1.0

    def test_set_volume_clamps_high(self, console: Console) -> None:
        """Should clamp volume above 1.0 to 1.0."""
        manager = AudioManager(console)

        manager.set_volume(1.5)
        assert manager.volume == 1.0

        manager.set_volume(10.0)
        assert manager.volume == 1.0

    def test_set_volume_clamps_low(self, console: Console) -> None:
        """Should clamp volume below 0.0 to 0.0."""
        manager = AudioManager(console)

        manager.set_volume(-0.5)
        assert manager.volume == 0.0

        manager.set_volume(-10.0)
        assert manager.volume == 0.0


class TestAudioManagerChannelAdjustment:
    """Tests for channel adjustment logic."""

    def test_upmix_mono_to_stereo(self, console: Console) -> None:
        """Should upmix mono audio to stereo by duplicating channel."""
        manager = AudioManager(console)
        mono_data = np.array([[0.5], [0.3], [0.1]], dtype=np.float32)

        result = manager._adjust_channels(mono_data, 2)

        assert result.shape == (3, 2)
        # Both channels should have same values as original mono
        np.testing.assert_array_equal(result[:, 0], result[:, 1])
        np.testing.assert_array_almost_equal(result[:, 0], [0.5, 0.3, 0.1])

    def test_downmix_stereo_to_mono(self, console: Console) -> None:
        """Should downmix stereo to mono by taking first channel."""
        manager = AudioManager(console)
        stereo_data = np.array([[0.5, 0.3], [0.2, 0.1]], dtype=np.float32)

        result = manager._adjust_channels(stereo_data, 1)

        assert result.shape == (2, 1)
        np.testing.assert_array_almost_equal(result[:, 0], [0.5, 0.2])

    def test_upmix_stereo_to_surround(self, console: Console) -> None:
        """Should upmix stereo to surround with padding."""
        manager = AudioManager(console)
        stereo_data = np.array([[0.5, 0.3], [0.2, 0.1]], dtype=np.float32)

        result = manager._adjust_channels(stereo_data, 6)  # 5.1 surround

        assert result.shape == (2, 6)
        # First two channels should be stereo duplicated
        np.testing.assert_array_almost_equal(result[:, 0], [0.5, 0.2])
        np.testing.assert_array_almost_equal(result[:, 1], [0.3, 0.1])

    def test_preserve_channels_when_matching(self, console: Console) -> None:
        """Should preserve audio when channels already match."""
        manager = AudioManager(console)
        stereo_data = np.array([[0.5, 0.3], [0.2, 0.1]], dtype=np.float32)

        result = manager._adjust_channels(stereo_data, 2)

        assert result.shape == (2, 2)
        np.testing.assert_array_almost_equal(result, stereo_data)

    def test_downmix_surround_to_stereo(self, console: Console) -> None:
        """Should downmix surround to stereo by taking first channels."""
        manager = AudioManager(console)
        surround_data = np.array(
            [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [0.6, 0.5, 0.4, 0.3, 0.2, 0.1]],
            dtype=np.float32,
        )

        result = manager._adjust_channels(surround_data, 2)

        assert result.shape == (2, 2)
        np.testing.assert_array_almost_equal(result[:, 0], [0.1, 0.6])
        np.testing.assert_array_almost_equal(result[:, 1], [0.2, 0.5])


class TestAudioManagerPlayback:
    """Tests for audio playback functionality."""

    def test_play_audio_without_output_device(self, console: Console, temp_sounds_dir: Path) -> None:
        """Should fail gracefully when no output device is set."""
        manager = AudioManager(console)
        audio_file = temp_sounds_dir / "sound1.wav"

        result = manager.play_audio(audio_file)

        assert result is False

    def test_play_audio_file_not_found(self, console: Console, mock_sounddevice: MagicMock, temp_dir: Path) -> None:
        """Should fail gracefully when audio file doesn't exist."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            manager.output_device_id = 0
            nonexistent_file = temp_dir / "nonexistent.wav"

            result = manager.play_audio(nonexistent_file)

            assert result is False

    def test_play_audio_success(
        self,
        console: Console,
        mock_sounddevice: MagicMock,
        mock_soundfile: MagicMock,
        temp_sounds_dir: Path,
    ) -> None:
        """Should play audio file successfully."""
        with patch("src.audio_manager.sd", mock_sounddevice), patch("src.audio_manager.sf", mock_soundfile):
            manager = AudioManager(console)
            manager.output_device_id = 0
            audio_file = temp_sounds_dir / "sound1.wav"

            result = manager.play_audio(audio_file)

            assert result is True
            mock_sounddevice.play.assert_called_once()

    def test_play_audio_applies_volume(
        self,
        console: Console,
        mock_sounddevice: MagicMock,
        mock_soundfile: MagicMock,
        temp_sounds_dir: Path,
    ) -> None:
        """Should apply volume scaling to audio data."""
        with patch("src.audio_manager.sd", mock_sounddevice), patch("src.audio_manager.sf", mock_soundfile):
            # Return predictable audio data
            original_data = np.ones((100, 2), dtype=np.float32)
            mock_soundfile.read.return_value = (original_data.copy(), 44100)

            manager = AudioManager(console)
            manager.output_device_id = 0
            manager.volume = 0.5
            audio_file = temp_sounds_dir / "sound1.wav"

            manager.play_audio(audio_file)

            # Check the data passed to sd.play has been scaled
            call_args = mock_sounddevice.play.call_args
            played_data = call_args[0][0]
            # Volume 0.5 should scale down the data
            assert np.max(played_data) <= 0.5

    def test_stop_audio(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should stop audio playback."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            manager.stop_audio()

            mock_sounddevice.stop.assert_called_once()


class TestAudioManagerPrintDevices:
    """Tests for print_devices method."""

    def test_print_devices_shows_all_devices(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should display all devices in formatted table."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            manager.print_devices()

            output = console.export_text()
            assert "Speakers" in output
            assert "CABLE Input" in output

    def test_print_devices_shows_selected_device(self, console: Console, mock_sounddevice: MagicMock) -> None:
        """Should indicate which device is currently selected."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            manager = AudioManager(console)
            manager.output_device_id = 2
            manager.print_devices()

            output = console.export_text()
            assert "SELECTED" in output


class TestAudioManagerIsPlaying:
    """Tests for is_playing method."""

    def test_is_playing_when_active(self, console: Console) -> None:
        """Should return True when audio stream is active."""
        mock_stream = MagicMock()
        mock_stream.active = True

        with patch("src.audio_manager.sd") as mock_sd:
            mock_sd.get_stream.return_value = mock_stream
            manager = AudioManager(console)

            assert manager.is_playing() is True

    def test_is_playing_when_not_active(self, console: Console) -> None:
        """Should return False when audio stream is not active."""
        mock_stream = MagicMock()
        mock_stream.active = False

        with patch("src.audio_manager.sd") as mock_sd:
            mock_sd.get_stream.return_value = mock_stream
            manager = AudioManager(console)

            assert manager.is_playing() is False

    def test_is_playing_when_no_stream(self, console: Console) -> None:
        """Should return False when there is no audio stream."""
        with patch("src.audio_manager.sd") as mock_sd:
            mock_sd.get_stream.return_value = None
            manager = AudioManager(console)

            assert manager.is_playing() is False
