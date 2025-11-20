# Copyright (c) 2025. All rights reserved.
"""CLI interface using rich-click for beautiful output."""

import sys

import rich_click as click
from pynput import keyboard
from rich.console import Console
from rich.panel import Panel

from .audio_manager import AudioManager
from .config import Config
from .soundboard import Soundboard

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.MAX_WIDTH = 100

console = Console()


def get_soundboard() -> tuple[Soundboard, AudioManager]:
    """Initialize and return soundboard and audio manager instances.

    Returns:
        Tuple containing initialized Soundboard and AudioManager instances.

    """
    config = Config()
    audio_manager = AudioManager(console)

    if config.output_device_id is not None:
        audio_manager.set_output_device(config.output_device_id)

    soundboard = Soundboard(audio_manager, config.sounds_dir, console)
    return soundboard, audio_manager


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0", prog_name="mu")
def cli(ctx: click.Context) -> None:
    """[bold cyan]MU Soundboard[/bold cyan].

    Play audio files through your microphone in games using hotkeys.
    Perfect for CS, Battlefield, COD, and more! 🎮🎵
    """
    if ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                "[bold cyan]MU Soundboard[/bold cyan]\n"
                "Play audio through your microphone in games!\n\n"
                "Run [bold]mu --help[/bold] to see all commands.",
                border_style="cyan",
            ),
        )


@cli.command()
def setup() -> None:
    """Configure your audio output device.

    Guides you through selecting a virtual audio device (like VB-Cable)
    to route sound to your microphone in games.
    """
    config = Config()
    audio_manager = AudioManager(console)

    console.print("\n[bold cyan]═══ Setup Wizard ═══[/bold cyan]\n")

    # Show all devices
    audio_manager.print_devices()

    # Check for virtual cable
    virtual_cable = audio_manager.find_virtual_cable()
    if virtual_cable is not None:
        console.print(
            f"[green]✓[/green] Found virtual audio device at ID [bold]{virtual_cable}[/bold]",
        )
        if click.confirm("Use this device?", default=True):
            audio_manager.set_output_device(virtual_cable)
            config.output_device_id = virtual_cable
            config.save()
            console.print("[green]✓[/green] Configuration saved!")
            return
    else:
        console.print("[yellow]⚠[/yellow] No virtual audio cable detected!")
        console.print("\n[dim]You need VB-Cable or similar virtual audio device.[/dim]")
        console.print("[dim]Download VB-Cable: https://vb-audio.com/Cable/[/dim]\n")

    # Manual selection
    device_id = click.prompt("Enter the device ID to use as output", type=int)
    if audio_manager.set_output_device(device_id):
        config.output_device_id = device_id
        config.save()
        console.print("[green]✓[/green] Configuration saved!")
    else:
        console.print("[red]✗[/red] Invalid device selection.")
        sys.exit(1)


@cli.command()
def devices() -> None:
    """List all available audio devices on your system."""
    audio_manager = AudioManager(console)
    audio_manager.print_devices()


@cli.command()
@click.argument("sound_name", required=False)
def play(sound_name: str | None) -> None:
    """Play a sound by name.

    If no sound name is provided, shows a list of available sounds.
    """
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found in sounds directory.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    if sound_name is None:
        soundboard.list_sounds()
        sound_name = str(click.prompt("Enter sound name to play", type=str))

    soundboard.play_sound(sound_name)


@cli.command()
def sounds() -> None:
    """List all available sounds in your library."""
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    soundboard.list_sounds()


@cli.command()
def hotkeys() -> None:
    """Show all configured hotkey bindings."""
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        sys.exit(1)

    soundboard.setup_default_hotkeys()
    soundboard.list_hotkeys()


@cli.command()
def listen() -> None:
    """Start listening for hotkeys (F1-F10).

    Activates the soundboard to respond to hotkey presses.
    Press ESC to stop listening.
    """
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    soundboard.setup_default_hotkeys()
    soundboard.list_hotkeys()

    console.print("\n[bold green]Soundboard Active![/bold green]")
    console.print("[dim]Press ESC to stop, or Ctrl+C to exit.[/dim]\n")

    soundboard.start_listening()

    # Wait for ESC key
    def on_press(key: keyboard.Key) -> bool | None:
        if key == keyboard.Key.esc:
            return False
        return None

    try:
        with keyboard.Listener(on_press=on_press) as listener:  # pyright: ignore[reportArgumentType]
            listener.join()
    except KeyboardInterrupt:
        pass
    finally:
        soundboard.stop_listening()
        console.print("\n[yellow]Stopped listening.[/yellow]")


@cli.command()
def stop() -> None:
    """Stop any currently playing sound."""
    soundboard, _ = get_soundboard()
    soundboard.stop_sound()
    console.print("[yellow]■[/yellow] Stopped current sound.")


def _handle_play_sound(soundboard: Soundboard) -> None:
    """Handle playing a sound by name."""
    sound_name = click.prompt("Enter sound name")
    soundboard.play_sound(sound_name)


def _handle_hotkey_listener(soundboard: Soundboard) -> None:
    """Handle starting the hotkey listener."""
    console.print("\n[bold green]Listening for hotkeys...[/bold green]")
    console.print("[dim]Press ESC to stop.[/dim]\n")
    soundboard.start_listening()

    def on_press(key: keyboard.Key) -> bool | None:
        if key == keyboard.Key.esc:
            return False
        return None

    with keyboard.Listener(on_press=on_press) as listener:  # pyright: ignore[reportArgumentType]
        listener.join()

    soundboard.stop_listening()
    console.print("[yellow]Stopped listening.[/yellow]")


def _handle_change_device(audio_manager: AudioManager) -> None:
    """Handle changing the output device."""
    audio_manager.print_devices()
    device_id = click.prompt("Enter device ID", type=int)
    if audio_manager.set_output_device(device_id):
        config = Config()
        config.output_device_id = device_id
        config.save()


def _show_menu() -> None:
    """Display the interactive menu."""
    console.print("\n[bold cyan]═══ Soundboard Menu ═══[/bold cyan]")
    console.print("1. List all sounds")
    console.print("2. Play sound by name")
    console.print("3. View hotkey bindings")
    console.print("4. Start hotkey listener")
    console.print("5. Stop current sound")
    console.print("6. List audio devices")
    console.print("7. Change output device")
    console.print("0. Exit")


@cli.command()
def interactive() -> None:  # noqa: C901
    """Launch interactive menu mode.

    Provides a text-based menu for exploring and using the soundboard.
    """
    soundboard, audio_manager = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    soundboard.setup_default_hotkeys()

    while True:
        _show_menu()
        choice = click.prompt("\nEnter your choice", type=str).strip()

        if choice == "1":
            soundboard.list_sounds()
        elif choice == "2":
            _handle_play_sound(soundboard)
        elif choice == "3":
            soundboard.list_hotkeys()
        elif choice == "4":
            _handle_hotkey_listener(soundboard)
        elif choice == "5":
            soundboard.stop_sound()
        elif choice == "6":
            audio_manager.print_devices()
        elif choice == "7":
            _handle_change_device(audio_manager)
        elif choice == "0":
            console.print("\n[cyan]Goodbye! 👋[/cyan]")
            break
        else:
            console.print("[red]Invalid choice.[/red]")


def main() -> None:
    """Entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)
    except (OSError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
