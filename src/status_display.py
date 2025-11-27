# Copyright (c) 2025. All rights reserved.
"""Status bar display for listen mode."""

import time
from datetime import UTC, datetime
from threading import Event, Thread

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .logging_config import get_logger

logger = get_logger(__name__)


class StatusDisplay:
    """Real-time status display for listen mode."""

    def __init__(
        self,
        console: Console,
        device_name: str,
        volume: float,
        sound_count: int,
        hotkey_count: int,
    ) -> None:
        """Initialize StatusDisplay.

        Args:
            console: Rich console for output
            device_name: Name of the output device
            volume: Current volume level (0.0 to 1.0)
            sound_count: Number of loaded sounds
            hotkey_count: Number of configured hotkeys

        """
        self.console = console
        self.device_name = device_name
        self.volume = volume
        self.sound_count = sound_count
        self.hotkey_count = hotkey_count

        self.start_time = datetime.now(tz=UTC)
        self.last_played: str | None = None
        self.last_played_key: str | None = None
        self.is_playing = False
        self._stop_event = Event()
        self._live: Live | None = None
        self._update_thread: Thread | None = None

        logger.debug("StatusDisplay initialized")

    def _format_uptime(self) -> str:
        """Format uptime as H:MM:SS or M:SS.

        Returns:
            Formatted uptime string

        """
        delta = datetime.now(tz=UTC) - self.start_time
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _build_display(self) -> Panel:
        """Build the status panel.

        Returns:
            Rich Panel with status information

        """
        # Volume bar
        vol_pct = int(self.volume * 100)
        vol_bars = int(self.volume * 10)
        vol_display = f"[{'█' * vol_bars}{'░' * (10 - vol_bars)}] {vol_pct}%"

        # Playing indicator
        if self.is_playing:
            status_icon = "[green]▶[/green]"
            status_text = f"Playing: [cyan]{self.last_played}[/cyan]"
        else:
            status_icon = "[cyan]●[/cyan]"
            status_text = "Ready"

        # Last played
        if self.last_played:
            last_played_text = f"{self.last_played}"
            if self.last_played_key:
                last_played_text += f" ({self.last_played_key.upper()})"
        else:
            last_played_text = "-"

        # Build content table
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()
        table.add_column(style="bold")
        table.add_column()

        table.add_row(
            "Device:",
            f"[cyan]{self.device_name[:30]}[/cyan]",
            "Volume:",
            vol_display,
        )
        table.add_row(
            "Status:",
            f"{status_icon} {status_text}",
            "Sounds:",
            f"[green]{self.sound_count}[/green] loaded",
        )
        table.add_row(
            "Last:",
            last_played_text,
            "Uptime:",
            f"[dim]{self._format_uptime()}[/dim]",
        )

        # Footer
        footer = Text()
        footer.append(f"Hotkeys: {self.hotkey_count} mapped", style="dim")
        footer.append("  │  ", style="dim")
        footer.append("Press ", style="dim")
        footer.append("ESC", style="bold yellow")
        footer.append(" to exit", style="dim")

        # Combine into panel
        content = Table.grid()
        content.add_row(table)
        content.add_row("")
        content.add_row(footer)

        return Panel(
            content,
            title="[bold cyan]🎮 MUC Soundboard Active[/bold cyan]",
            border_style="cyan",
        )

    def update_playing(self, sound_name: str, hotkey: str | None = None) -> None:
        """Update the last played sound.

        Args:
            sound_name: Name of the sound being played
            hotkey: Optional hotkey that triggered playback

        """
        self.last_played = sound_name
        self.last_played_key = hotkey
        self.is_playing = True
        logger.debug(f"Status updated: playing '{sound_name}'")

    def update_stopped(self) -> None:
        """Mark playback as stopped."""
        self.is_playing = False

    def update_volume(self, volume: float) -> None:
        """Update the volume display.

        Args:
            volume: New volume level (0.0 to 1.0)

        """
        self.volume = volume

    def start(self) -> None:
        """Start the live display."""
        logger.debug("Starting status display")

        self._live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=2,
            transient=False,
        )
        self._live.start()

        # Start update thread
        def update_loop() -> None:
            while not self._stop_event.is_set():
                if self._live:
                    self._live.update(self._build_display())
                time.sleep(0.5)

        self._update_thread = Thread(target=update_loop, daemon=True)
        self._update_thread.start()

    def stop(self) -> None:
        """Stop the live display."""
        logger.debug("Stopping status display")

        self._stop_event.set()
        if self._live:
            self._live.stop()
            self._live = None
