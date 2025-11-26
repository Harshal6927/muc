# Copyright (c) 2025. All rights reserved.
"""Unit tests for Soundboard class."""

from pathlib import Path
from unittest.mock import MagicMock

from rich.console import Console

from src.soundboard import Soundboard


class TestSoundboardScanning:
    """Tests for sound file scanning functionality."""

    def test_scans_supported_formats(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should find all supported audio formats."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        assert "sound1" in soundboard.sounds  # .wav
        assert "sound2" in soundboard.sounds  # .mp3
        assert "sound3" in soundboard.sounds  # .ogg
        assert "sound4" in soundboard.sounds  # .flac in subdirectory

    def test_scans_recursively(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should find sounds in subdirectories."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        # sound4.flac is in subdir/
        assert "sound4" in soundboard.sounds
        assert soundboard.sounds["sound4"] == temp_sounds_dir / "subdir" / "sound4.flac"

    def test_ignores_unsupported_formats(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should ignore non-audio files."""
        # Create non-audio files
        (temp_sounds_dir / "readme.txt").touch()
        (temp_sounds_dir / "image.png").touch()
        (temp_sounds_dir / "data.json").touch()

        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        assert "readme" not in soundboard.sounds
        assert "image" not in soundboard.sounds
        assert "data" not in soundboard.sounds

    def test_handles_missing_directory(self, console: Console, temp_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should handle non-existent sounds directory gracefully."""
        missing_dir = temp_dir / "nonexistent"

        soundboard = Soundboard(mock_audio_manager, missing_dir, console)

        assert len(soundboard.sounds) == 0

    def test_handles_empty_directory(self, console: Console, temp_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should handle empty sounds directory."""
        empty_dir = temp_dir / "empty_sounds"
        empty_dir.mkdir()

        soundboard = Soundboard(mock_audio_manager, empty_dir, console)

        assert len(soundboard.sounds) == 0

    def test_uses_stem_as_sound_name(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should use filename without extension as sound name."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        assert "sound1" in soundboard.sounds
        assert soundboard.sounds["sound1"] == temp_sounds_dir / "sound1.wav"

    def test_supports_m4a_format(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should support .m4a audio format."""
        (temp_sounds_dir / "music.m4a").touch()

        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        assert "music" in soundboard.sounds


class TestSoundboardHotkeys:
    """Tests for hotkey functionality."""

    def test_setup_default_hotkeys(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should assign F1-F10 to first 10 sounds alphabetically."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.setup_default_hotkeys()

        assert "<f1>" in soundboard.hotkeys
        # Sounds should be alphabetically ordered: sound1, sound2, sound3, sound4
        assert soundboard.hotkeys["<f1>"] == "sound1"
        assert soundboard.hotkeys["<f2>"] == "sound2"
        assert soundboard.hotkeys["<f3>"] == "sound3"
        assert soundboard.hotkeys["<f4>"] == "sound4"

    def test_setup_default_hotkeys_limits_to_10(
        self,
        console: Console,
        temp_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should only assign hotkeys to first 10 sounds."""
        sounds_dir = temp_dir / "many_sounds"
        sounds_dir.mkdir()

        # Create 15 sound files
        for i in range(1, 16):
            (sounds_dir / f"sound{i:02d}.wav").touch()

        soundboard = Soundboard(mock_audio_manager, sounds_dir, console)
        soundboard.setup_default_hotkeys()

        # Only F1-F10 should be assigned
        assert len(soundboard.hotkeys) == 10
        assert "<f10>" in soundboard.hotkeys
        assert "<f11>" not in soundboard.hotkeys

    def test_set_hotkey_valid_sound(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should allow custom hotkey binding for valid sound."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        result = soundboard.set_hotkey("<ctrl>+<alt>+a", "sound1")

        assert result is True
        assert soundboard.hotkeys["<ctrl>+<alt>+a"] == "sound1"

    def test_set_hotkey_invalid_sound(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should reject hotkey binding for non-existent sound."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        result = soundboard.set_hotkey("<f1>", "nonexistent")

        assert result is False
        assert "<f1>" not in soundboard.hotkeys

    def test_set_hotkey_overwrites_existing(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should overwrite existing hotkey binding."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.set_hotkey("<f1>", "sound1")
        soundboard.set_hotkey("<f1>", "sound2")

        assert soundboard.hotkeys["<f1>"] == "sound2"


class TestSoundboardPlayback:
    """Tests for sound playback."""

    def test_play_sound_valid(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should play valid sound through audio manager."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        result = soundboard.play_sound("sound1")

        assert result is True
        mock_audio_manager.play_audio.assert_called_once()

    def test_play_sound_with_correct_path(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should pass correct audio file path to audio manager."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        soundboard.play_sound("sound1")

        expected_path = temp_sounds_dir / "sound1.wav"
        mock_audio_manager.play_audio.assert_called_with(expected_path, blocking=False)

    def test_play_sound_invalid(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should return False for non-existent sound."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        result = soundboard.play_sound("nonexistent")

        assert result is False
        mock_audio_manager.play_audio.assert_not_called()

    def test_play_sound_blocking(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should pass blocking parameter to audio manager."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        soundboard.play_sound("sound1", blocking=True)

        expected_path = temp_sounds_dir / "sound1.wav"
        mock_audio_manager.play_audio.assert_called_with(expected_path, blocking=True)

    def test_stop_sound(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should stop audio through audio manager."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)

        soundboard.stop_sound()

        mock_audio_manager.stop_audio.assert_called_once()


class TestSoundboardListing:
    """Tests for sound listing functionality."""

    def test_list_sounds_shows_all(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should display all sounds in table."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.list_sounds()

        output = console.export_text()
        assert "sound1" in output
        assert "sound2" in output
        assert "sound3" in output

    def test_list_sounds_empty(self, console: Console, temp_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should show message when no sounds available."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        soundboard = Soundboard(mock_audio_manager, empty_dir, console)
        soundboard.list_sounds()

        output = console.export_text()
        assert "No sounds available" in output

    def test_list_hotkeys_shows_bindings(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should display all hotkey bindings."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.setup_default_hotkeys()
        soundboard.list_hotkeys()

        output = console.export_text()
        assert "<F1>" in output.upper()
        assert "sound1" in output

    def test_list_hotkeys_empty(self, console: Console, temp_sounds_dir: Path, mock_audio_manager: MagicMock) -> None:
        """Should show message when no hotkeys configured."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        # Don't call setup_default_hotkeys()
        soundboard.list_hotkeys()

        output = console.export_text()
        assert "No hotkeys configured" in output


class TestSoundboardListener:
    """Tests for hotkey listener functionality."""

    def test_start_listening_without_hotkeys(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should warn when starting listener without hotkeys."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        # Don't setup hotkeys

        soundboard.start_listening()

        output = console.export_text()
        assert "No hotkeys configured" in output

    def test_start_listening_creates_listener(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
        mock_pynput: MagicMock,
    ) -> None:
        """Should create GlobalHotKeys listener when starting."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.setup_default_hotkeys()

        soundboard.start_listening()

        mock_pynput.GlobalHotKeys.assert_called_once()

    def test_stop_listening_stops_listener(
        self,
        console: Console,
        temp_sounds_dir: Path,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Should stop listener when stop_listening is called."""
        soundboard = Soundboard(mock_audio_manager, temp_sounds_dir, console)
        soundboard.setup_default_hotkeys()
        soundboard.start_listening()

        soundboard.stop_listening()

        assert soundboard.listener is None
