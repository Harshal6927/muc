# Copyright (c) 2025. All rights reserved.
"""Audio device management and playback functionality."""

from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from rich.console import Console
from rich.table import Table


class AudioManager:
    """Manages audio devices and playback operations."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the AudioManager.

        Args:
            console: Rich console for output (creates new if None)

        """
        self.console = console or Console()
        self.current_stream = None
        self.output_device_id: int | None = None

    def list_devices(self):  # noqa: ANN201, PLR6301
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
        devices = self.list_devices()
        if 0 <= device_id < len(devices):
            device = sd.query_devices(device_id)
            if device["max_output_channels"] > 0:  # pyright: ignore[reportArgumentType, reportCallIssue]
                self.output_device_id = device_id
                self.console.print(
                    f"[green]✓[/green] Output device set to: [bold]{device['name']}[/bold]",  # pyright: ignore[reportArgumentType, reportCallIssue]
                )
                return True
            self.console.print(
                f"[red]✗[/red] Device {device_id} has no output channels.",
            )
            return False
        self.console.print(f"[red]✗[/red] Invalid device ID: {device_id}")
        return False

    def play_audio(self, audio_file: Path, *, blocking: bool = False) -> bool:
        """Play an audio file through the selected output device.

        Args:
            audio_file: Path to the audio file
            blocking: If True, wait for playback to finish

        Returns:
            True if playback started successfully, False otherwise.

        """
        if self.output_device_id is None:
            self.console.print(
                "[yellow]⚠[/yellow] No output device selected. Use set_output_device() first.",
            )
            return False

        if not audio_file.exists():
            self.console.print(f"[red]✗[/red] Audio file not found: {audio_file}")
            return False

        try:
            # Stop any currently playing audio
            self.stop_audio()

            # Load and play the audio file
            data, samplerate = sf.read(str(audio_file))  # pyright: ignore[reportGeneralTypeIssues]

            # Ensure data is in the correct format
            if len(data.shape) == 1:
                # Mono audio
                data = data.reshape(-1, 1)

            # Get device info to match channels
            device_info = sd.query_devices(self.output_device_id)
            max_channels = device_info["max_output_channels"]  # pyright: ignore[reportCallIssue, reportArgumentType]

            # Adjust channels if needed
            if data.shape[1] < max_channels:
                # Duplicate channels if we have fewer than device supports
                data = np.tile(data, (1, max_channels // data.shape[1]))
            elif data.shape[1] > max_channels:
                # Take only the channels we need
                data = data[:, :max_channels]

            sd.play(data, samplerate, device=self.output_device_id)

            if blocking:
                sd.wait()
        except (OSError, RuntimeError) as e:
            self.console.print(f"[red]Error:[/red] {e}")
            return False
        else:
            self.console.print(
                f"[green]▶[/green] Playing: [bold]{audio_file.name}[/bold]",
            )
            return True

    def stop_audio(self) -> None:
        """Stop any currently playing audio."""
        try:
            sd.stop()
        except (OSError, RuntimeError) as e:
            self.console.print(f"[red]Error stopping audio:[/red] {e}")

    def is_playing(self) -> bool:  # noqa: PLR6301
        """Check if audio is currently playing.

        Returns:
            True if audio is currently playing, False otherwise.

        """
        return sd.get_stream().active if sd.get_stream() else False
