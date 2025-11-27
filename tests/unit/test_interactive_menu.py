# Copyright (c) 2025. All rights reserved.
"""Tests for the interactive_menu module."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.interactive_menu import InteractiveMenu


class TestInteractiveMenu:
    """Tests for InteractiveMenu class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console.

        Returns:
            Mocked Console instance.

        """
        return MagicMock(spec=Console)

    @pytest.fixture
    def mock_soundboard(self) -> MagicMock:
        """Create a mock soundboard.

        Returns:
            Mocked Soundboard instance.

        """
        soundboard = MagicMock()
        soundboard.sounds = {
            "airhorn": Path("/path/to/airhorn.mp3"),
            "rickroll": Path("/path/to/rickroll.mp3"),
        }
        soundboard.hotkeys = {"<f1>": "airhorn", "<f2>": "rickroll"}
        return soundboard

    @pytest.fixture
    def mock_audio_manager(self) -> MagicMock:
        """Create a mock audio manager.

        Returns:
            Mocked AudioManager instance.

        """
        manager = MagicMock()
        manager.volume = 0.75
        manager.output_device_id = 1
        manager.is_playing.return_value = False
        return manager

    @pytest.fixture
    def menu(
        self,
        mock_console: MagicMock,
        mock_soundboard: MagicMock,
        mock_audio_manager: MagicMock,
    ) -> InteractiveMenu:
        """Create an InteractiveMenu instance for testing.

        Args:
            mock_console: Mocked console.
            mock_soundboard: Mocked soundboard.
            mock_audio_manager: Mocked audio manager.

        Returns:
            InteractiveMenu instance.

        """
        return InteractiveMenu(mock_console, mock_soundboard, mock_audio_manager)

    def test_initialization(
        self,
        menu: InteractiveMenu,
        mock_console: MagicMock,
    ) -> None:
        """Test InteractiveMenu initializes correctly."""
        assert menu.console is mock_console
        assert menu.last_played is None
        assert menu.last_played_time is None

    def test_build_header_returns_panel(self, menu: InteractiveMenu) -> None:
        """Test that _build_header returns a Panel."""
        with patch("src.interactive_menu.sd"):
            panel = menu._build_header()
            assert isinstance(panel, Panel)

    def test_build_menu_returns_table(self, menu: InteractiveMenu) -> None:
        """Test that _build_menu returns a Table."""
        table = menu._build_menu()
        assert isinstance(table, Table)

    def test_build_footer_no_last_played(self, menu: InteractiveMenu) -> None:
        """Test footer when no sound has been played."""
        footer = menu._build_footer()
        assert "Status: Ready" in footer

    def test_build_footer_with_last_played(self, menu: InteractiveMenu) -> None:
        """Test footer when a sound has been played."""
        menu.last_played = "airhorn"
        menu.last_played_time = datetime.now(tz=UTC)
        footer = menu._build_footer()
        assert "airhorn" in footer

    def test_build_footer_when_playing(
        self,
        menu: InteractiveMenu,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Test footer when audio is playing."""
        mock_audio_manager.is_playing.return_value = True
        footer = menu._build_footer()
        assert "Playing" in footer

    def test_do_play_updates_last_played(
        self,
        menu: InteractiveMenu,
        mock_soundboard: MagicMock,
    ) -> None:
        """Test that playing a sound updates last_played."""
        menu._do_play("airhorn")
        mock_soundboard.play_sound.assert_called_once_with("airhorn", blocking=True)
        assert menu.last_played == "airhorn"
        assert menu.last_played_time is not None

    def test_stop_sound(
        self,
        menu: InteractiveMenu,
        mock_soundboard: MagicMock,
        mock_console: MagicMock,
    ) -> None:
        """Test stopping a sound."""
        menu._stop_sound()
        mock_soundboard.stop_sound.assert_called_once()
        mock_console.print.assert_called()

    def test_list_sounds(
        self,
        menu: InteractiveMenu,
        mock_soundboard: MagicMock,
    ) -> None:
        """Test listing sounds."""
        menu._list_sounds()
        mock_soundboard.list_sounds.assert_called_once()

    def test_show_hotkeys(
        self,
        menu: InteractiveMenu,
        mock_soundboard: MagicMock,
    ) -> None:
        """Test showing hotkeys."""
        menu._show_hotkeys()
        mock_soundboard.list_hotkeys.assert_called_once()

    def test_list_devices(
        self,
        menu: InteractiveMenu,
        mock_audio_manager: MagicMock,
    ) -> None:
        """Test listing devices."""
        menu._list_devices()
        mock_audio_manager.print_devices.assert_called_once()


class TestInteractiveMenuSearch:
    """Tests for search functionality in InteractiveMenu."""

    @pytest.fixture
    def menu_with_sounds(self) -> InteractiveMenu:
        """Create a menu with mock sounds.

        Returns:
            InteractiveMenu instance with mocked dependencies.

        """
        console = MagicMock()  # No spec to allow mock assertions
        soundboard = MagicMock()
        soundboard.sounds = {
            "airhorn": Path("/path/to/airhorn.mp3"),
            "rickroll": Path("/path/to/rickroll.mp3"),
            "explosion": Path("/path/to/explosion.mp3"),
        }
        audio_manager = MagicMock()
        audio_manager.volume = 0.75
        audio_manager.output_device_id = 1
        return InteractiveMenu(console, soundboard, audio_manager)

    @patch("src.interactive_menu.click")
    @patch("src.interactive_menu.search_sounds")
    def test_search_with_no_results(
        self,
        mock_search: MagicMock,
        mock_click: MagicMock,
        menu_with_sounds: InteractiveMenu,
    ) -> None:
        """Test search when no results found."""
        mock_click.prompt.return_value = "xyz"
        mock_search.return_value = []

        menu_with_sounds._search()

        mock_search.assert_called_once()
        menu_with_sounds.console.print.assert_called()  # pyright: ignore[reportAttributeAccessIssue]
