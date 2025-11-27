# Copyright (c) 2025. All rights reserved.
"""Enhanced interactive menu for MUC Soundboard."""

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import click
import sounddevice as sd
from pynput import keyboard
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .logging_config import get_logger
from .metadata import MetadataManager
from .search import SearchResult, search_sounds

if TYPE_CHECKING:
    from .audio_manager import AudioManager
    from .soundboard import Soundboard

logger = get_logger(__name__)


class InteractiveMenu:
    """Enhanced interactive menu for MUC."""

    def __init__(
        self,
        console: Console,
        soundboard: "Soundboard",
        audio_manager: "AudioManager",
    ) -> None:
        """Initialize InteractiveMenu.

        Args:
            console: Rich console for output
            soundboard: Soundboard instance
            audio_manager: AudioManager instance

        """
        self.console = console
        self.soundboard = soundboard
        self.audio_manager = audio_manager
        self.metadata = MetadataManager()
        self.last_played: str | None = None
        self.last_played_time: datetime | None = None

        logger.debug("InteractiveMenu initialized")

    def _build_header(self) -> Panel:
        """Build the status header panel.

        Returns:
            Rich Panel with status information

        """
        # Volume bar
        vol_pct = int(self.audio_manager.volume * 100)
        vol_bars = int(self.audio_manager.volume * 10)
        vol_display = f"[{'█' * vol_bars}{'░' * (10 - vol_bars)}] {vol_pct}%"

        # Device name
        device_name = "Not configured"
        if self.audio_manager.output_device_id is not None:
            try:
                device = sd.query_devices(self.audio_manager.output_device_id)
                device_name = str(device["name"])[:25]  # pyright: ignore[reportArgumentType, reportCallIssue]
            except (sd.PortAudioError, ValueError):
                logger.debug("Could not query device name")

        # Count favorites
        fav_count = sum(1 for name in self.soundboard.sounds if self.metadata.get_metadata(name).favorite)

        header_table = Table.grid(padding=(0, 3))
        header_table.add_column()
        header_table.add_column()
        header_table.add_row(
            f"Device: [cyan]{device_name}[/cyan]",
            f"Volume: {vol_display}",
        )
        header_table.add_row(
            f"Sounds: [green]{len(self.soundboard.sounds)}[/green] loaded",
            f"Favorites: [yellow]{fav_count}[/yellow]",
        )

        return Panel(
            header_table,
            title="[bold cyan]🎮 MUC Soundboard[/bold cyan]",
            border_style="cyan",
        )

    def _build_menu(self) -> Table:
        """Build the menu options table.

        Returns:
            Rich Table with menu options

        """
        menu = Table.grid(padding=(0, 4))
        menu.add_column(width=25)
        menu.add_column(width=25)
        menu.add_column(width=25)

        options = [
            ("[1]", "📋", "List Sounds"),
            ("[2]", "▶ ", "Play Sound"),
            ("[3]", "⌨ ", "Hotkey Bindings"),
            ("[4]", "👂", "Start Listening"),
            ("[5]", "⏹ ", "Stop Playing"),
            ("[6]", "🔊", "Audio Devices"),
            ("[7]", "⚙ ", "Change Device"),
            ("[8]", "🔉", "Adjust Volume"),
            ("[9]", "🔀", "Auto-play"),
            ("[s]", "🔍", "Search Sounds"),
            ("[0]", "🚪", "Exit"),
        ]

        # Layout in 3 columns
        for i in range(0, len(options), 3):
            row = []
            for j in range(3):
                if i + j < len(options):
                    key, icon, label = options[i + j]
                    row.append(f"[bold]{key}[/bold] {icon} {label}")
                else:
                    row.append("")
            menu.add_row(*row)

        return menu

    def _build_footer(self) -> str:
        """Build the status footer.

        Returns:
            Footer string with status info

        """
        parts = []

        # Last played
        if self.last_played and self.last_played_time:
            elapsed = (datetime.now(tz=UTC) - self.last_played_time).seconds
            parts.append(f"Last: [cyan]{self.last_played}[/cyan] ({elapsed}s ago)")

        # Status
        if self.audio_manager.is_playing():
            parts.append("Status: [green]Playing[/green]")
        else:
            parts.append("Status: Ready")

        return "    ".join(parts) if parts else ""

    def display(self) -> str:
        """Display the menu and get user choice.

        Returns:
            User's menu choice

        """
        self.console.clear()
        self.console.print(self._build_header())
        self.console.print()
        self.console.print(self._build_menu())
        self.console.print()

        footer = self._build_footer()
        if footer:
            self.console.print(f"  {footer}")
            self.console.print()

        return (
            click.prompt(
                "> Enter choice",
                type=str,
                show_choices=False,
            )
            .strip()
            .lower()
        )

    def run(self) -> None:
        """Run the interactive menu loop."""
        actions = {
            "1": self._list_sounds,
            "2": self._play_sound,
            "3": self._show_hotkeys,
            "4": self._start_listening,
            "5": self._stop_sound,
            "6": self._list_devices,
            "7": self._change_device,
            "8": self._adjust_volume,
            "9": self._auto_play,
            "s": self._search,
        }

        while True:
            choice = self.display()

            if choice == "0":
                self.console.print("\n[cyan]Goodbye! 👋[/cyan]")
                break

            action = actions.get(choice)
            if action:
                action()
                click.pause("Press any key to continue...")
            else:
                self.console.print("[red]Invalid choice[/red]")

    def _list_sounds(self) -> None:
        """List all available sounds."""
        self.soundboard.list_sounds()

    def _play_sound(self) -> None:
        """Play a sound by name with search support."""
        sound_name = click.prompt("Enter sound name (or search term)")

        # Check if exact match
        if sound_name in self.soundboard.sounds:
            self._do_play(sound_name)
            return

        # Try fuzzy search
        tags = {name: self.metadata.get_metadata(name).tags for name in self.soundboard.sounds}
        results = search_sounds(sound_name, self.soundboard.sounds, tags, limit=5)

        if not results:
            self.console.print(f"[red]✗[/red] No sounds matching '{sound_name}'")
            return

        if len(results) == 1:
            if click.confirm(f"Play '{results[0].name}'?", default=True):
                self._do_play(results[0].name)
            return

        # Show results and let user pick
        self._show_search_results(results, sound_name)
        choice = click.prompt("Enter number to play (or 0 to cancel)", type=int, default=0)
        if 1 <= choice <= len(results):
            self._do_play(results[choice - 1].name)

    def _do_play(self, sound_name: str) -> None:
        """Play a sound and update status.

        Args:
            sound_name: Name of the sound to play

        """
        self.soundboard.play_sound(sound_name, blocking=True)
        self.last_played = sound_name
        self.last_played_time = datetime.now(tz=UTC)

    def _show_search_results(self, results: list[SearchResult], query: str) -> None:
        """Display search results in a table.

        Args:
            results: List of search results
            query: Original search query

        """
        table = Table(title=f"Results for '{query}'", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Sound Name", style="white")
        table.add_column("Match", style="cyan")

        for idx, result in enumerate(results, 1):
            table.add_row(str(idx), result.name, result.match_type)

        self.console.print(table)

    def _show_hotkeys(self) -> None:
        """Show configured hotkey bindings."""
        self.soundboard.list_hotkeys()

    def _start_listening(self) -> None:
        """Start the hotkey listener."""
        self.console.print("\n[bold green]Listening for hotkeys...[/bold green]")
        self.console.print("[dim]Press ESC to stop.[/dim]\n")
        self.soundboard.start_listening()

        def on_press(key: keyboard.Key) -> bool | None:
            if key == keyboard.Key.esc:
                return False
            return None

        with keyboard.Listener(on_press=on_press) as listener:  # pyright: ignore[reportArgumentType]
            listener.join()

        self.soundboard.stop_listening()
        self.console.print("[yellow]Stopped listening.[/yellow]")

    def _stop_sound(self) -> None:
        """Stop currently playing audio."""
        self.soundboard.stop_sound()
        self.console.print("[yellow]⏹[/yellow] Stopped.")

    def _list_devices(self) -> None:
        """List all audio devices."""
        self.audio_manager.print_devices()

    def _change_device(self) -> None:
        """Change the output device."""
        self.audio_manager.print_devices()
        device_id = click.prompt("Enter device ID", type=int)
        if self.audio_manager.set_output_device(device_id):
            config = Config()
            config.output_device_id = device_id
            config.save()

    def _adjust_volume(self) -> None:
        """Adjust the playback volume."""
        percentage = int(self.audio_manager.volume * 100)
        self.console.print(f"[cyan]Current volume:[/cyan] {percentage}%")
        volume_input = click.prompt(
            "Enter volume level (0-100)",
            type=click.IntRange(0, 100),
        )
        self.audio_manager.set_volume(volume_input / 100.0)
        config = Config()
        config.volume = self.audio_manager.volume
        config.save()

    def _auto_play(self) -> None:
        """Auto-play all sounds."""
        with contextlib.suppress(KeyboardInterrupt):
            self.soundboard.play_all_sounds()

    def _search(self) -> None:
        """Search for sounds."""
        query = click.prompt("Search for")

        tags = {name: self.metadata.get_metadata(name).tags for name in self.soundboard.sounds}
        results = search_sounds(query, self.soundboard.sounds, tags)

        if not results:
            self.console.print(f"[yellow]⚠[/yellow] No sounds matching '{query}'")
            return

        # Display results
        table = Table(title=f"Search Results for '{query}'", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Sound Name", style="white")
        table.add_column("Match", style="cyan")
        table.add_column("Score", style="green", justify="right")

        for idx, result in enumerate(results, 1):
            score_pct = f"{int(result.score * 100)}%"
            table.add_row(str(idx), result.name, result.match_type, score_pct)

        self.console.print(table)

        # Offer to play
        if len(results) == 1:
            if click.confirm(f"Play '{results[0].name}'?"):
                self._do_play(results[0].name)
        elif click.confirm("Play a result?"):
            choice = click.prompt("Enter number", type=int, default=1)
            if 1 <= choice <= len(results):
                self._do_play(results[choice - 1].name)
