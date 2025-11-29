# Copyright (c) 2025. All rights reserved.
"""Audio device management and playback functionality."""

import time
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from .cache import CachedAudio, LRUAudioCache
from .exceptions import (
    AudioFileCorruptedError,
    DeviceDisconnectedError,
    DeviceNoOutputError,
    DeviceNotFoundError,
)
from .logging_config import get_logger
from .validators import validate_device

logger = get_logger(__name__)


class AudioManager:
    """Manages audio devices and playback operations."""

    DEFAULT_CACHE_SIZE_MB = 100

    def __init__(
        self,
        console: Console | None = None,
        cache_enabled: bool = True,
        cache_size_mb: int | None = None,
    ) -> None:
        """Initialize the AudioManager.

        Args:
            console: Rich console for output (creates new if None)
            cache_enabled: Whether to enable audio caching (default: True)
            cache_size_mb: Maximum cache size in MB (default: 100)

        """
        self.console = console or Console()
        self.current_stream = None
        self.output_device_id: int | None = None
        self.volume: float = 1.0

        # Caching setup
        self.cache_enabled = cache_enabled
        cache_size = (cache_size_mb or self.DEFAULT_CACHE_SIZE_MB) * 1024 * 1024
        self._cache = LRUAudioCache(max_size_bytes=cache_size)

        logger.debug(f"AudioManager initialized (cache_enabled={cache_enabled})")

    def list_devices(self):  # noqa: ANN201
        """List all available audio devices.

        Returns:
            Device list from sounddevice query.

        """
        return sd.query_devices()

    def find_virtual_cable(self) -> int | None:
        """Find VB-Cable or similar virtual audio device.

        Returns:
            The device ID if found, None otherwise.

        """
        devices = self.list_devices()
        keywords = ["cable", "virtual", "vb-audio", "voicemeeter"]

        for idx in range(len(devices)):
            device = sd.query_devices(idx)
            device_name = str(device["name"]).lower()  # pyright: ignore[reportArgumentType, reportCallIssue]
            if any(keyword in device_name for keyword in keywords) and device["max_output_channels"] > 0:  # pyright: ignore[reportArgumentType, reportCallIssue]
                return idx
        return None

    def print_devices(self) -> None:
        """Print all audio devices with their IDs in a formatted table."""
        table = Table(
            title="Available Audio Devices",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="dim", width=4, justify="right")
        table.add_column("Device Name", style="white")
        table.add_column("Inputs", justify="center", width=8)
        table.add_column("Outputs", justify="center", width=8)
        table.add_column("Status", justify="center", width=10)

        devices = self.list_devices()
        for idx in range(len(devices)):
            device = sd.query_devices(idx)
            status = "[green]SELECTED[/green]" if self.output_device_id == idx else ""

            table.add_row(
                str(idx),
                str(device["name"]),  # pyright: ignore[reportArgumentType, reportCallIssue]
                str(device["max_input_channels"]),  # pyright: ignore[reportArgumentType, reportCallIssue]
                str(device["max_output_channels"]),  # pyright: ignore[reportArgumentType, reportCallIssue]
                status,
            )

        self.console.print(table)

    def set_output_device(self, device_id: int) -> bool:
        """Set the output device for audio playback.

        Args:
            device_id: ID of the device to set as output

        Returns:
            True if device was set successfully, False otherwise.

        """
        try:
            device_info = validate_device(device_id)
            self.output_device_id = device_id
        except DeviceNotFoundError as e:
            logger.warning(f"Device not found: {e}")
            self.console.print(f"[red]✗[/red] {e.message}")
            self.console.print(f"[dim]💡 {e.suggestion}[/dim]")
            return False
        except DeviceNoOutputError as e:
            logger.warning(f"Device has no output: {e}")
            self.console.print(f"[red]✗[/red] {e.message}")
            self.console.print(f"[dim]💡 {e.suggestion}[/dim]")
            return False
        else:
            self.console.print(
                f"Output device set to: [bold]{device_info.name} (ID: {device_id})[/bold]",
            )
            return True

    def set_volume(self, volume: float) -> None:
        """Set the playback volume level.

        Args:
            volume: Volume level from 0.0 (mute) to 1.0 (full volume)

        """
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        percentage = int(self.volume * 100)
        logger.debug(f"Volume set to {percentage}%")
        self.console.print(f"[cyan]♪[/cyan] Volume set to {percentage}%")

    @staticmethod
    def _adjust_channels(data: np.ndarray, max_channels: int) -> np.ndarray:
        """Adjust audio channels to match the output device.

        Args:
            data: Audio data array
            max_channels: Target number of channels

        Returns:
            Adjusted audio data array

        """
        if data.shape[1] < max_channels:
            # Duplicate channels to fill as much as possible
            tile_count = max_channels // data.shape[1]
            data = np.tile(data, (1, tile_count))

            # If we still don't have enough channels (e.g. 2 -> 5), pad with silence
            current_channels = data.shape[1]
            if current_channels < max_channels:
                padding = np.zeros((data.shape[0], max_channels - current_channels))
                data = np.hstack((data, padding))

        elif data.shape[1] > max_channels:
            # Take only the channels we need
            data = data[:, :max_channels]

        return data

    def _load_and_prepare_audio(
        self,
        audio_file: Path,
        sound_volume: float,
    ) -> tuple[np.ndarray, int] | None:
        """Load and prepare audio data for playback.

        Args:
            audio_file: Path to the audio file
            sound_volume: Per-sound volume multiplier

        Returns:
            Tuple of (data, samplerate) or None if loading failed

        """
        cache_key = str(audio_file)

        # Try cache first
        if self.cache_enabled:
            cached = self._cache.get(cache_key)
            if cached:
                data = cached.data.copy()  # Copy to avoid modifying cached data
                samplerate = cached.samplerate
                logger.debug(f"Cache hit for {audio_file.name}")
            else:
                # Load from disk and cache
                try:
                    data, samplerate = sf.read(str(audio_file))  # pyright: ignore[reportGeneralTypeIssues]
                except sf.LibsndfileError as e:
                    logger.exception("Failed to read audio file")
                    error = AudioFileCorruptedError(
                        f"Cannot read audio file: {audio_file.name}",
                        details={"path": str(audio_file), "error": str(e)},
                    )
                    self.console.print(f"[red]✗[/red] {error.message}")
                    self.console.print(f"[dim]💡 {error.suggestion}[/dim]")
                    return None

                # Cache the loaded audio (store original data)
                cached_audio = CachedAudio(
                    data=data.copy() if isinstance(data, np.ndarray) else np.array(data),
                    samplerate=samplerate,
                    size_bytes=data.nbytes if isinstance(data, np.ndarray) else 0,
                    path=audio_file,
                )
                self._cache.put(cache_key, cached_audio)
                logger.debug(f"Cached {audio_file.name}")
        else:
            # Load without caching
            try:
                data, samplerate = sf.read(str(audio_file))  # pyright: ignore[reportGeneralTypeIssues]

            except sf.LibsndfileError as e:
                logger.exception("Failed to read audio file")
                error = AudioFileCorruptedError(
                    f"Cannot read audio file: {audio_file.name}",
                    details={"path": str(audio_file), "error": str(e)},
                )
                self.console.print(f"[red]✗[/red] {error.message}")
                self.console.print(f"[dim]💡 {error.suggestion}[/dim]")
                return None

        # Ensure data is in the correct format
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        # Get device info to match channels
        device_info = sd.query_devices(self.output_device_id)
        max_channels = device_info["max_output_channels"]  # pyright: ignore[reportCallIssue, reportArgumentType]

        logger.debug(
            f"Audio info: duration={len(data) / samplerate:.2f}s, rate={samplerate}, channels={data.shape[1]}",
        )

        # Adjust channels if needed
        data = self._adjust_channels(data, max_channels)

        # Apply combined volume scaling: global x sound-specific
        final_volume = self.volume * sound_volume
        data *= final_volume

        return data, samplerate

    def play_audio(
        self,
        audio_file: Path,
        *,
        blocking: bool = False,
        sound_volume: float = 1.0,
        show_progress: bool = True,
    ) -> bool:
        """Play an audio file through the selected output device.

        Args:
            audio_file: Path to the audio file
            blocking: If True, wait for playback to finish
            sound_volume: Per-sound volume multiplier (0.0 to 2.0), combined with global volume
            show_progress: If True and blocking, show a progress bar

        Returns:
            True if playback started successfully, False otherwise.

        """
        if self.output_device_id is None:
            logger.warning("No output device selected")
            self.console.print(
                "[yellow]⚠[/yellow] No output device selected. Use 'muc setup' first.",
            )
            return False

        if not audio_file.exists():
            logger.warning(f"Audio file not found: {audio_file}")
            self.console.print(f"[red]✗[/red] Audio file not found: {audio_file}")
            return False

        # Verify device is still available before playback
        try:
            validate_device(self.output_device_id)
        except (DeviceNotFoundError, DeviceNoOutputError) as e:
            logger.exception("Device validation failed")
            self.console.print(f"[red]✗[/red] {e.message}")
            self.console.print(f"[dim]💡 {e.suggestion}[/dim]")
            return False

        # Stop any currently playing audio
        self.stop_audio()

        logger.debug(f"Loading audio file: {audio_file}")

        # Load and prepare audio
        result = self._load_and_prepare_audio(audio_file, sound_volume)
        if result is None:
            return False
        data, samplerate = result

        try:
            logger.debug(f"Starting playback to device {self.output_device_id}")
            sd.play(data, samplerate, device=self.output_device_id)

            if blocking:
                # Calculate duration for progress bar
                duration_seconds = len(data) / samplerate

                if show_progress and self.console.is_terminal:
                    return self._show_progress(audio_file.name, duration_seconds)

                # Use polling loop instead of sd.wait() to allow KeyboardInterrupt
                while sd.get_stream() and sd.get_stream().active:
                    time.sleep(0.1)

        except sd.PortAudioError as e:
            # Device disconnection or error during playback
            if "device" in str(e).lower() or "stream" in str(e).lower():
                logger.exception("Device error during playback")
                error = DeviceDisconnectedError(
                    details={"device_id": self.output_device_id, "error": str(e)},
                )
                self.console.print(f"[red]✗[/red] {error.message}")
                self.console.print(f"[dim]💡 {error.suggestion}[/dim]")
            else:
                self.console.print(f"[red]Error:[/red] {e}")
            return False
        except (OSError, RuntimeError) as e:
            logger.exception("Playback error")
            self.console.print(f"[red]Error:[/red] {e}")
            return False
        else:
            self.console.print(
                f"[green]▶[/green] Playing: [bold]{audio_file.name}[/bold]",
            )
            return True

    def _format_time(self, seconds: float) -> str:
        """Format seconds as M:SS.

        Args:
            seconds: Number of seconds

        Returns:
            Formatted time string

        """
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _show_progress(self, filename: str, duration: float) -> bool:
        """Display progress bar during playback.

        Args:
            filename: Name of the audio file
            duration: Total duration in seconds

        Returns:
            True if completed, False if interrupted

        """
        with Progress(
            TextColumn("[bold cyan]▶[/bold cyan]"),
            TextColumn("[white]{task.fields[filename]}[/white]"),
            BarColumn(bar_width=30, style="cyan", complete_style="green"),
            TaskProgressColumn(),
            TextColumn("•"),
            TextColumn("[cyan]{task.fields[elapsed]}[/cyan]"),
            TextColumn("/"),
            TextColumn("[dim]{task.fields[total_time]}[/dim]"),
            TextColumn("•"),
            TextColumn("[dim]Ctrl+C to stop[/dim]"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task(
                "Playing",
                total=duration,
                filename=filename,
                elapsed="0:00",
                total_time=self._format_time(duration),
            )

            start_time = time.time()

            try:
                while sd.get_stream() and sd.get_stream().active:
                    elapsed = time.time() - start_time
                    progress.update(
                        task,
                        completed=min(elapsed, duration),
                        elapsed=self._format_time(elapsed),
                    )
                    time.sleep(0.1)  # 10 FPS update rate

            except KeyboardInterrupt:
                self.stop_audio()
                self.console.print("\n[yellow]⏹[/yellow] Playback stopped")
                return False
            else:
                # Ensure 100% on completion
                progress.update(
                    task,
                    completed=duration,
                    elapsed=self._format_time(duration),
                )
                return True

    def stop_audio(self) -> None:
        """Stop any currently playing audio."""
        try:
            sd.stop()
            logger.debug("Audio playback stopped")
        except (OSError, RuntimeError) as e:
            logger.exception("Error stopping audio")
            self.console.print(f"[red]Error stopping audio:[/red] {e}")

    def is_playing(self) -> bool:
        """Check if audio is currently playing.

        Returns:
            True if audio is currently playing, False otherwise.

        """
        return sd.get_stream().active if sd.get_stream() else False

    # ─────────────────────────────────────────────────────────────────────────
    # Cache Management Methods
    # ─────────────────────────────────────────────────────────────────────────

    def preload_sounds(self, paths: list[Path]) -> int:
        """Pre-load sounds into cache.

        Args:
            paths: List of paths to audio files

        Returns:
            Number of sounds successfully preloaded

        """
        if not self.cache_enabled:
            logger.warning("Cache is disabled, skipping preload")
            return 0
        return self._cache.preload(paths)

    def clear_cache(self) -> None:
        """Clear the audio cache."""
        self._cache.clear()
        self.console.print("[green]✓[/green] Audio cache cleared")

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        """
        return self._cache.stats

    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching.

        Args:
            enabled: Whether to enable caching

        """
        self.cache_enabled = enabled
        if not enabled:
            self._cache.clear()
        logger.info(f"Cache {'enabled' if enabled else 'disabled'}")

    def set_cache_size(self, size_mb: int) -> None:
        """Set the cache size limit.

        Args:
            size_mb: Maximum cache size in megabytes

        """
        # Create new cache with new size (clears existing cache)
        self._cache = LRUAudioCache(max_size_bytes=size_mb * 1024 * 1024)
        logger.info(f"Cache size set to {size_mb} MB")
