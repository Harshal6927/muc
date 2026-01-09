# Copyright (c) 2025. All rights reserved.
"""Integration tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.profile_manager import Profile


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner.

    Returns:
        CliRunner: A Click testing utility for invoking CLI commands.

    """
    return CliRunner()


@pytest.fixture
def mock_profile_manager(temp_sounds_dir: Path) -> MagicMock:
    """Create a mock ProfileManager object.

    Returns:
        MagicMock: A mock ProfileManager object.

    """
    mock = MagicMock()
    profile = Profile(
        name="default",
        settings={
            "output_device_id": None,
            "volume": 1.0,
            "sounds_dir": str(temp_sounds_dir),
            "sounds_dirs": [str(temp_sounds_dir)],
            "hotkeys": {},
            "hotkey_mode": "merged",
        },
    )
    mock.get_active_profile.return_value = profile
    mock.active_profile_name = "default"
    return mock


@pytest.fixture(autouse=True)
def use_mock_audio_validation(mock_audio_validation: MagicMock) -> MagicMock:
    """Use mock audio validation for all CLI tests.

    Returns:
        MagicMock: The mock audio validation object.

    """
    return mock_audio_validation


class TestCLIDevices:
    """Tests for 'muc devices' command."""

    def test_devices_command_output(self, cli_runner: CliRunner, mock_sounddevice: MagicMock) -> None:
        """Should display device table."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            result = cli_runner.invoke(cli, ["devices"])

        assert result.exit_code == 0
        assert "Speakers" in result.output
        assert "CABLE Input" in result.output

    def test_devices_shows_ids(self, cli_runner: CliRunner, mock_sounddevice: MagicMock) -> None:
        """Should show device IDs in output."""
        with patch("src.audio_manager.sd", mock_sounddevice):
            result = cli_runner.invoke(cli, ["devices"])

        assert result.exit_code == 0
        # Device IDs should be present
        assert "0" in result.output


class TestCLIVolume:
    """Tests for 'muc volume' command."""

    def test_volume_display(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should display current volume."""
        # Update profile to have specific volume
        mock_profile_manager.get_active_profile.return_value.volume = 0.75

        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["volume"])

        assert result.exit_code == 0
        assert "75%" in result.output

    def test_volume_set(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should set volume level."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["volume", "0.5"])

        assert result.exit_code == 0
        mock_profile_manager.save_profile.assert_called_once()

    def test_volume_invalid_range(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should reject volume outside valid range."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["volume", "1.5"])

        # Click should reject values outside FloatRange(0.0, 1.0)
        assert result.exit_code != 0


class TestCLISounds:
    """Tests for 'muc sounds' command."""

    def test_sounds_lists_files(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should list available sounds."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["sounds"])

        assert result.exit_code == 0
        assert "sound1" in result.output

    def test_sounds_empty_directory(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should show error for empty sounds directory."""
        empty_dir = temp_dir / "empty_sounds"
        empty_dir.mkdir()

        mock_pm = MagicMock()
        profile = Profile(
            name="default",
            settings={
                "output_device_id": None,
                "volume": 1.0,
                "sounds_dir": str(empty_dir),
                "sounds_dirs": [str(empty_dir)],
            },
        )
        mock_pm.get_active_profile.return_value = profile

        with (
            patch("src.cli.ProfileManager", return_value=mock_pm),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["sounds"])

        assert result.exit_code == 1
        assert "No sounds found" in result.output


class TestCLIHotkeys:
    """Tests for 'muc hotkeys' command."""

    def test_hotkeys_displays_bindings(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should display hotkey bindings."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["hotkeys"])

        assert result.exit_code == 0
        # Should show F1-F4 for the 4 sounds
        assert "F1" in result.output.upper()


class TestCLIPlay:
    """Tests for 'muc play' command."""

    def test_play_with_sound_name(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
        mock_soundfile: MagicMock,
    ) -> None:
        """Should play specified sound."""
        mock_profile_manager.get_active_profile.return_value.output_device_id = 0

        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
            patch("src.audio_manager.sf", mock_soundfile),
        ):
            result = cli_runner.invoke(cli, ["play", "sound1"])

        assert result.exit_code == 0

    def test_play_without_output_device(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should warn when no output device is set."""
        mock_profile_manager.get_active_profile.return_value.output_device_id = None

        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["play", "sound1"])

        # Should show error about no output device
        assert "No output device" in result.output or result.exit_code == 1

    def test_play_nonexistent_sound(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should handle non-existent sound gracefully."""
        mock_profile_manager.get_active_profile.return_value.output_device_id = 0

        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["play", "nonexistent"])

        assert "not found" in result.output.lower()


class TestCLIStop:
    """Tests for 'muc stop' command."""

    def test_stop_command(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should stop currently playing sound."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["stop"])

        assert result.exit_code == 0
        assert "Stopped" in result.output


class TestCLISetup:
    """Tests for 'muc setup' command."""

    def test_setup_finds_virtual_cable(
        self,
        cli_runner: CliRunner,
        mock_profile_manager: MagicMock,
        mock_sounddevice: MagicMock,
    ) -> None:
        """Should find and suggest virtual cable during setup."""
        with (
            patch("src.cli.ProfileManager", return_value=mock_profile_manager),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            # Answer 'yes' to use detected device
            result = cli_runner.invoke(cli, ["setup"], input="y\n")

        assert result.exit_code == 0
        assert "virtual audio device" in result.output.lower() or "CABLE" in result.output


class TestCLIAuto:
    """Tests for 'muc auto' command."""

    def test_auto_no_sounds(self, cli_runner: CliRunner, temp_dir: Path, mock_sounddevice: MagicMock) -> None:
        """Should show error when no sounds available."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        mock_pm = MagicMock()
        profile = Profile(
            name="default",
            settings={
                "output_device_id": 0,
                "volume": 1.0,
                "sounds_dir": str(empty_dir),
                "sounds_dirs": [str(empty_dir)],
            },
        )
        mock_pm.get_active_profile.return_value = profile

        with (
            patch("src.cli.ProfileManager", return_value=mock_pm),
            patch("src.audio_manager.sd", mock_sounddevice),
        ):
            result = cli_runner.invoke(cli, ["auto"])

        assert result.exit_code == 1
        assert "No sounds found" in result.output


class TestCLIMainCommand:
    """Tests for main 'muc' command."""

    def test_cli_without_command(self, cli_runner: CliRunner) -> None:
        """Should show welcome panel when run without command."""
        result = cli_runner.invoke(cli)

        assert result.exit_code == 0
        assert "MUC Soundboard" in result.output

    def test_cli_help(self, cli_runner: CliRunner) -> None:
        """Should show help information."""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "setup" in result.output
        assert "devices" in result.output
        assert "sounds" in result.output

    def test_cli_version(self, cli_runner: CliRunner) -> None:
        """Should show version information."""
        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.5.1" in result.output
