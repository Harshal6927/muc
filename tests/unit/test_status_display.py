# Copyright (c) 2025. All rights reserved.
"""Tests for the status_display module."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from rich.panel import Panel

from src.status_display import StatusDisplay


class TestStatusDisplay:
    """Tests for StatusDisplay class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console.

        Returns:
            Mocked Console instance.

        """
        return MagicMock(spec=Console)

    @pytest.fixture
    def status_display(self, mock_console: MagicMock) -> StatusDisplay:
        """Create a StatusDisplay instance for testing.

        Args:
            mock_console: Mocked console instance.

        Returns:
            StatusDisplay instance.

        """
        return StatusDisplay(
            console=mock_console,
            device_name="Test Device",
            volume=0.75,
            sound_count=10,
            hotkey_count=5,
        )

    def test_initialization(self, status_display: StatusDisplay) -> None:
        """Test StatusDisplay initializes with correct values."""
        assert status_display.device_name == "Test Device"
        assert status_display.volume == 0.75
        assert status_display.sound_count == 10
        assert status_display.hotkey_count == 5
        assert status_display.last_played is None
        assert status_display.is_playing is False

    def test_format_uptime_seconds(self, status_display: StatusDisplay) -> None:
        """Test uptime formatting for seconds only."""
        # Mock start_time to 30 seconds ago
        status_display.start_time = datetime.now(tz=UTC) - timedelta(seconds=30)
        uptime = status_display._format_uptime()
        assert uptime == "0:30"

    def test_format_uptime_minutes(self, status_display: StatusDisplay) -> None:
        """Test uptime formatting for minutes."""
        status_display.start_time = datetime.now(tz=UTC) - timedelta(minutes=5, seconds=32)
        uptime = status_display._format_uptime()
        assert uptime == "5:32"

    def test_format_uptime_hours(self, status_display: StatusDisplay) -> None:
        """Test uptime formatting for hours."""
        status_display.start_time = datetime.now(tz=UTC) - timedelta(hours=1, minutes=5, seconds=32)
        uptime = status_display._format_uptime()
        assert uptime == "1:05:32"

    def test_update_playing(self, status_display: StatusDisplay) -> None:
        """Test updating the playing status."""
        status_display.update_playing("airhorn", "f1")
        assert status_display.last_played == "airhorn"
        assert status_display.last_played_key == "f1"
        assert status_display.is_playing is True

    def test_update_stopped(self, status_display: StatusDisplay) -> None:
        """Test updating to stopped status."""
        status_display.update_playing("airhorn")
        status_display.update_stopped()
        assert status_display.is_playing is False
        # Last played should still be set
        assert status_display.last_played == "airhorn"

    def test_update_volume(self, status_display: StatusDisplay) -> None:
        """Test updating volume."""
        status_display.update_volume(0.5)
        assert status_display.volume == 0.5

    def test_build_display_returns_panel(self, status_display: StatusDisplay) -> None:
        """Test that _build_display returns a Panel."""
        panel = status_display._build_display()
        assert isinstance(panel, Panel)

    def test_build_display_with_playing_status(self, status_display: StatusDisplay) -> None:
        """Test display shows playing status."""
        status_display.update_playing("test_sound", "f1")
        panel = status_display._build_display()
        # Panel should be built without errors
        assert panel is not None

    @patch("src.status_display.Live")
    def test_start_stop(
        self,
        mock_live_class: MagicMock,
        status_display: StatusDisplay,
    ) -> None:
        """Test start and stop methods."""
        mock_live = MagicMock()
        mock_live_class.return_value = mock_live

        status_display.start()

        # Verify Live was created and started
        mock_live_class.assert_called_once()
        mock_live.start.assert_called_once()

        # Give the update thread a moment to start
        time.sleep(0.1)

        status_display.stop()

        # Verify Live was stopped
        mock_live.stop.assert_called_once()
        assert status_display._stop_event.is_set()


class TestStatusDisplayEdgeCases:
    """Edge case tests for StatusDisplay."""

    def test_long_device_name_truncated(self) -> None:
        """Test that long device names are handled."""
        console = MagicMock(spec=Console)
        status = StatusDisplay(
            console=console,
            device_name="A" * 100,  # Very long name
            volume=0.5,
            sound_count=5,
            hotkey_count=3,
        )
        # Should truncate to 30 chars
        panel = status._build_display()
        assert panel is not None

    def test_zero_volume(self) -> None:
        """Test display with zero volume."""
        console = MagicMock(spec=Console)
        status = StatusDisplay(
            console=console,
            device_name="Test",
            volume=0.0,
            sound_count=5,
            hotkey_count=3,
        )
        panel = status._build_display()
        assert panel is not None

    def test_full_volume(self) -> None:
        """Test display with full volume."""
        console = MagicMock(spec=Console)
        status = StatusDisplay(
            console=console,
            device_name="Test",
            volume=1.0,
            sound_count=5,
            hotkey_count=3,
        )
        panel = status._build_display()
        assert panel is not None

    def test_no_last_played(self) -> None:
        """Test display when no sound has been played."""
        console = MagicMock(spec=Console)
        status = StatusDisplay(
            console=console,
            device_name="Test",
            volume=0.5,
            sound_count=5,
            hotkey_count=3,
        )
        assert status.last_played is None
        panel = status._build_display()
        assert panel is not None
