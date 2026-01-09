# Copyright (c) 2025. All rights reserved.
"""CLI interface using rich-click for beautiful output."""

import contextlib
import sys
from pathlib import Path

import rich_click as click
import sounddevice as sd
from pynput import keyboard
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.audio_manager import AudioManager
from src.audio_tools import AudioNormalizer, AudioTrimmer
from src.config_transfer import ConfigTransfer
from src.downloader import YouTubeDownloader, check_ffmpeg_available, check_yt_dlp_available
from src.exceptions import MUCError
from src.hotkey_manager import HotkeyManager
from src.interactive_menu import InteractiveMenu
from src.logging_config import init_logging
from src.metadata import MetadataManager
from src.profile_manager import ProfileManager
from src.queue_manager import QueueManager
from src.search import search_sounds
from src.soundboard import Soundboard
from src.sounds_directories import SoundsDirectoryManager
from src.status_display import StatusDisplay
from src.validators import validate_audio_file

# Configure rich-click
click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
click.rich_click.MAX_WIDTH = 100

console = Console()


def get_soundboard() -> tuple[Soundboard, AudioManager]:
    """Initialize and return soundboard and audio manager instances.

    Uses the active profile's settings for configuration.

    Returns:
        Tuple containing initialized Soundboard and AudioManager instances.

    """
    pm = ProfileManager()
    profile = pm.get_active_profile()

    audio_manager = AudioManager(console)
    metadata_manager = MetadataManager()

    if profile.output_device_id is not None:
        audio_manager.set_output_device(profile.output_device_id)

    # Set volume from profile (silently, without printing)
    audio_manager.volume = profile.volume

    # Get sounds directories from profile
    sounds_dirs = profile.sounds_dirs
    if sounds_dirs:
        sounds_dirs_paths = [Path(d) for d in sounds_dirs]
    elif profile.sounds_dir:
        sounds_dirs_paths = [Path(profile.sounds_dir)]
    else:
        sounds_dirs_paths = [Path.cwd() / "sounds"]

    # Create hotkey manager with profile manager
    hotkey_manager = HotkeyManager(pm)

    soundboard = Soundboard(
        audio_manager,
        console=console,
        metadata_manager=metadata_manager,
        hotkey_manager=hotkey_manager,
        sounds_dirs=sounds_dirs_paths,
    )
    return soundboard, audio_manager


@click.group(invoke_without_command=True)
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
@click.version_option(version="0.5.1", prog_name="muc")
def cli(ctx: click.Context, debug: bool) -> None:
    """[bold cyan]MUC Soundboard[/bold cyan].

    Play audio files through your microphone in games using hotkeys.
    Perfect for CS, Battlefield, COD, and more! 🎮🎵
    """
    # Initialize logging
    init_logging(debug=debug)

    # Store debug flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                "[bold cyan]MUC Soundboard[/bold cyan]\n"
                "Play audio through your microphone in games!\n\n"
                "Run [bold]muc --help[/bold] to see all commands.",
                border_style="cyan",
            ),
        )


@cli.command()
def setup() -> None:
    """Configure your audio output device.

    Guides you through selecting a virtual audio device (like VB-Cable)
    to route sound to your microphone in games.
    """
    pm = ProfileManager()
    profile = pm.get_active_profile()
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
            profile.output_device_id = virtual_cable
            pm.save_profile(profile)
            console.print("[green]✓[/green] Configuration saved!")
            return
    else:
        console.print("[yellow]⚠[/yellow] No virtual audio cable detected!")
        console.print("\n[dim]You need VB-Cable or similar virtual audio device.[/dim]")
        console.print("[dim]Download VB-Cable: https://vb-audio.com/Cable/[/dim]\n")

    # Manual selection
    device_id = click.prompt("Enter the device ID to use as output", type=int)
    if audio_manager.set_output_device(device_id):
        profile.output_device_id = device_id
        pm.save_profile(profile)
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

    soundboard.play_sound(sound_name, blocking=True)


@cli.command()
@click.option("--tag", "-t", "filter_tag", help="Filter by tag (comma-separated for multiple)")
@click.option("--favorites", "-f", is_flag=True, help="Show only favorites")
def sounds(filter_tag: str | None, favorites: bool) -> None:
    """List all available sounds in your library.

    Use --tag to filter by tags, --favorites to show only favorites.
    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    # Get all sound names
    sound_names = sorted(soundboard.sounds.keys())

    # Filter by tag if specified
    if filter_tag:
        tags = [t.strip() for t in filter_tag.split(",")]
        tagged_sounds = set(metadata.get_sounds_by_tags(tags))
        sound_names = [s for s in sound_names if s in tagged_sounds]
        if not sound_names:
            console.print(f"[yellow]⚠[/yellow] No sounds found with tag(s): {filter_tag}")
            return

    # Filter by favorites if specified
    if favorites:
        favorite_sounds = set(metadata.get_favorites())
        sound_names = [s for s in sound_names if s in favorite_sounds]
        if not sound_names:
            console.print("[yellow]⚠[/yellow] No favorite sounds yet. Use 'muc favorite <sound>' to add.")
            return

    # Build table with extended columns
    title = "★ Favorite Sounds" if favorites else "Available Sounds"
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Sound Name", style="white")
    table.add_column("Vol", style="cyan", justify="center", width=5)
    table.add_column("Tags", style="blue", max_width=20)
    table.add_column("Hotkey", style="green", justify="center", width=10)
    table.add_column("Plays", style="dim", justify="right", width=6)

    # Setup hotkeys to show in table
    soundboard.setup_hotkeys()

    for idx, name in enumerate(sound_names, 1):
        meta = metadata.get_metadata(name)

        # Volume indicator
        vol_display = f"{int(meta.volume * 100)}%"

        # Tags
        tags_str = ", ".join(meta.tags[:3]) if meta.tags else "-"
        if len(meta.tags) > 3:
            tags_str += "..."

        # Hotkey
        hotkey = next((k for k, v in soundboard.hotkeys.items() if v == name), None)
        hotkey_display = hotkey.upper() if hotkey else "-"

        # Favorite indicator
        fav_indicator = "★ " if meta.favorite else ""
        name_display = f"{fav_indicator}{name}"

        table.add_row(
            str(idx),
            name_display,
            vol_display,
            tags_str,
            hotkey_display,
            str(meta.play_count),
        )

    console.print(table)


@cli.command()
def hotkeys() -> None:
    """Show all configured hotkey bindings."""
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        sys.exit(1)

    soundboard.setup_hotkeys()
    soundboard.list_hotkeys()


# ─────────────────────────────────────────────────────────────────────────────
# Tag Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("sound_name")
@click.argument("tags", nargs=-1, required=True)
def tag(sound_name: str, tags: tuple[str, ...]) -> None:
    """Add tags to a sound.

    Example: muc tag airhorn meme loud effect
    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    added = [tag_name for tag_name in tags if metadata.add_tag(sound_name, tag_name)]

    if added:
        console.print(f"[green]✓[/green] Added tags to '{sound_name}': {', '.join(added)}")
    else:
        console.print(f"[yellow]⚠[/yellow] All tags already exist on '{sound_name}'")


@cli.command()
@click.argument("sound_name")
@click.argument("tags", nargs=-1, required=True)
def untag(sound_name: str, tags: tuple[str, ...]) -> None:
    """Remove tags from a sound.

    Example: muc untag airhorn loud
    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    removed = [tag_name for tag_name in tags if metadata.remove_tag(sound_name, tag_name)]

    if removed:
        console.print(f"[green]✓[/green] Removed tags from '{sound_name}': {', '.join(removed)}")
    else:
        console.print(f"[yellow]⚠[/yellow] None of the specified tags were on '{sound_name}'")


@cli.command()
def tags() -> None:
    """List all tags with their usage counts."""
    metadata = MetadataManager()
    tag_counts = metadata.get_all_tags_with_counts()

    if not tag_counts:
        console.print("[yellow]⚠[/yellow] No tags found. Use 'muc tag <sound> <tags>' to add tags.")
        return

    table = Table(title="Tags", show_header=True, header_style="bold cyan")
    table.add_column("Tag", style="blue")
    table.add_column("Sounds", style="white", justify="right")

    for tag_name, count in sorted(tag_counts.items()):
        table.add_row(tag_name, str(count))

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# Favorites Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("sound_name")
@click.option("--on", "set_on", is_flag=True, help="Set as favorite")
@click.option("--off", "set_off", is_flag=True, help="Remove from favorites")
def favorite(sound_name: str, set_on: bool, set_off: bool) -> None:
    """Toggle or set favorite status for a sound.

    Examples:
        muc favorite airhorn          # Toggle
        muc favorite airhorn --on     # Add to favorites
        muc favorite airhorn --off    # Remove from favorites

    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    if set_on:
        metadata.set_favorite(sound_name, is_favorite=True)
        is_fav = True
    elif set_off:
        metadata.set_favorite(sound_name, is_favorite=False)
        is_fav = False
    else:
        is_fav = metadata.toggle_favorite(sound_name)

    status = "[yellow]★[/yellow] Favorite" if is_fav else "Not favorite"
    console.print(f"[green]✓[/green] '{sound_name}' is now: {status}")


@cli.command()
def favorites() -> None:
    """List all favorite sounds."""
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    favorites_list = [name for name in soundboard.sounds if metadata.get_metadata(name).favorite]

    if not favorites_list:
        console.print("[yellow]⚠[/yellow] No favorites yet. Use 'muc favorite <sound>' to add.")
        return

    soundboard.setup_hotkeys()

    table = Table(title="★ Favorite Sounds", show_header=True, header_style="bold yellow")
    table.add_column("#", style="dim", width=4)
    table.add_column("Sound Name", style="white")
    table.add_column("Hotkey", style="green")

    for idx, name in enumerate(sorted(favorites_list), 1):
        hotkey = next((k for k, v in soundboard.hotkeys.items() if v == name), "-")
        table.add_row(str(idx), name, hotkey.upper() if hotkey != "-" else "-")

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# Per-Sound Volume and Info Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.command(name="sound-volume")
@click.argument("sound_name")
@click.argument("level", type=click.FloatRange(0.0, 2.0), required=False)
def sound_volume(sound_name: str, level: float | None) -> None:
    """Set or display volume for a specific sound.

    Volume range: 0.0 (mute) to 2.0 (200%).
    Final volume = sound_volume x global_volume

    Examples:
        muc sound-volume airhorn 0.5   # Set to 50%
        muc sound-volume airhorn       # Show current

    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    meta = metadata.get_metadata(sound_name)

    if level is None:
        percentage = int(meta.volume * 100)
        console.print(f"[cyan]Volume for '{sound_name}':[/cyan] {percentage}%")
    else:
        metadata.set_volume(sound_name, level)
        percentage = int(level * 100)
        console.print(f"[green]✓[/green] Volume for '{sound_name}' set to {percentage}%")


@cli.command()
@click.argument("sound_name")
@click.option("--preview", "-p", is_flag=True, help="Play first 3 seconds")
def info(sound_name: str, preview: bool) -> None:
    """Show detailed information about a sound.

    Example: muc info airhorn
    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    audio_path = soundboard.sounds[sound_name]
    meta = metadata.get_metadata(sound_name)

    # Get audio file info
    try:
        file_info = validate_audio_file(audio_path)
    except MUCError as e:
        console.print(f"[red]✗[/red] Cannot read file: {e.message}")
        sys.exit(1)

    # Format duration
    duration_mins = int(file_info.duration // 60)
    duration_secs = file_info.duration % 60
    duration_str = f"{duration_mins}:{duration_secs:05.2f}"

    # File size
    file_size = audio_path.stat().st_size
    size_str = f"{file_size / (1024 * 1024):.1f} MB" if file_size > 1024 * 1024 else f"{file_size / 1024:.1f} KB"

    # Last played formatting
    last_played_str = meta.last_played.strftime("%Y-%m-%d %H:%M") if meta.last_played else "Never"

    # Build info panel
    info_text = f"""[bold cyan]{sound_name}[/bold cyan]

[bold]File Information[/bold]
├── Path: {audio_path}
├── Format: {file_info.format}
├── Size: {size_str}
├── Duration: {duration_str}
├── Sample Rate: {file_info.sample_rate} Hz
└── Channels: {file_info.channels} ({"Stereo" if file_info.channels >= 2 else "Mono"})

[bold]Metadata[/bold]
├── Tags: {", ".join(meta.tags) if meta.tags else "None"}
├── Volume: {int(meta.volume * 100)}%
├── Favorite: {"Yes ★" if meta.favorite else "No"}
├── Play Count: {meta.play_count}
└── Last Played: {last_played_str}"""

    console.print(Panel(info_text, title=f"Sound Info: {sound_name}", border_style="cyan"))

    if preview:
        console.print("\n[dim]Playing preview...[/dim]")
        soundboard.play_sound(sound_name, blocking=True)


# ─────────────────────────────────────────────────────────────────────────────
# Custom Hotkey Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("hotkey")
@click.argument("sound_name")
def bind(hotkey: str, sound_name: str) -> None:
    """Bind a hotkey to a sound.

    Hotkey format: <modifier>+<modifier>+<key>

    Examples:
        muc bind f1 airhorn
        muc bind "<ctrl>+<shift>+a" applause
        muc bind "<alt>+1" explosion

    Supported modifiers: ctrl, alt, shift, cmd (Mac)
    Supported keys: a-z, 0-9, f1-f12, space, etc.

    """
    soundboard, _ = get_soundboard()
    hotkey_mgr = HotkeyManager()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    # Normalize hotkey format
    normalized = hotkey_mgr.normalize_hotkey(hotkey)

    if not normalized:
        console.print(f"[red]✗[/red] Invalid hotkey format: {hotkey}")
        console.print("[dim]Use format like: f1, <ctrl>+a, <ctrl>+<shift>+1[/dim]")
        sys.exit(1)

    # Check for conflicts
    existing = hotkey_mgr.get_binding(normalized)
    if existing and existing != sound_name:
        console.print(f"[yellow]⚠[/yellow] Hotkey {normalized} is bound to '{existing}'")
        if not click.confirm("Override?"):
            return

    hotkey_mgr.bind(normalized, sound_name)
    console.print(f"[green]✓[/green] Bound {normalized.upper()} → {sound_name}")


@cli.command()
@click.argument("hotkey_or_sound")
def unbind(hotkey_or_sound: str) -> None:
    """Unbind a hotkey or all hotkeys for a sound.

    Examples:
        muc unbind f1                    # Unbind F1 key
        muc unbind airhorn               # Unbind all keys for 'airhorn'

    """
    soundboard, _ = get_soundboard()
    hotkey_mgr = HotkeyManager()

    # Check if it's a sound name
    if hotkey_or_sound in soundboard.sounds:
        count = hotkey_mgr.unbind_sound(hotkey_or_sound)
        if count > 0:
            console.print(f"[green]✓[/green] Unbound {count} hotkey(s) from '{hotkey_or_sound}'")
        else:
            console.print(f"[yellow]⚠[/yellow] No hotkeys bound to '{hotkey_or_sound}'")
    else:
        # Treat as hotkey
        normalized = hotkey_mgr.normalize_hotkey(hotkey_or_sound)
        if normalized and hotkey_mgr.unbind(normalized):
            console.print(f"[green]✓[/green] Unbound {normalized.upper()}")
        else:
            console.print(f"[yellow]⚠[/yellow] No binding found for {hotkey_or_sound}")


@cli.command(name="hotkeys-reset")
def hotkeys_reset() -> None:
    """Clear all custom hotkey bindings."""
    hotkey_mgr = HotkeyManager()
    count = hotkey_mgr.clear_all()
    console.print(f"[green]✓[/green] Cleared {count} custom hotkey binding(s)")


# ─────────────────────────────────────────────────────────────────────────────
# Queue Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group()
def queue() -> None:
    """Manage the sound playback queue."""


@queue.command(name="add")
@click.argument("sound_names", nargs=-1, required=True)
def queue_add(sound_names: tuple[str, ...]) -> None:
    """Add sounds to the queue.

    Example: muc queue add airhorn rickroll explosion
    """
    soundboard, _ = get_soundboard()
    queue_mgr = QueueManager()

    # Validate sound names
    valid_sounds = []
    for name in sound_names:
        if name in soundboard.sounds:
            valid_sounds.append(name)
        else:
            console.print(f"[yellow]⚠[/yellow] Sound '{name}' not found, skipping")

    if valid_sounds:
        queue_mgr.add(*valid_sounds)
        console.print(f"[green]✓[/green] Added {len(valid_sounds)} sound(s) to queue")
        console.print(f"[dim]Queue size: {queue_mgr.size()}[/dim]")
    else:
        console.print("[red]✗[/red] No valid sounds to add")


@queue.command(name="show")
def queue_show() -> None:
    """Display the current queue."""
    queue_mgr = QueueManager()
    items = queue_mgr.peek()

    if not items:
        console.print("[yellow]⚠[/yellow] Queue is empty")
        return

    table = Table(title="Sound Queue", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Sound Name", style="white")

    for idx, name in enumerate(items, 1):
        table.add_row(str(idx), name)

    console.print(table)


@queue.command(name="clear")
def queue_clear() -> None:
    """Clear the queue."""
    queue_mgr = QueueManager()
    count = queue_mgr.clear()
    console.print(f"[green]✓[/green] Cleared {count} sound(s) from queue")


@queue.command(name="play")
def queue_play() -> None:
    """Play all sounds in the queue sequentially."""
    soundboard, _ = get_soundboard()
    queue_mgr = QueueManager()

    if queue_mgr.is_empty():
        console.print("[yellow]⚠[/yellow] Queue is empty")
        return

    total = queue_mgr.size()
    console.print(f"\n[bold cyan]Playing {total} sounds from queue...[/bold cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        idx = 1
        while True:
            sound_name = queue_mgr.next()
            if sound_name is None:
                break
            console.print(f"[cyan][{idx}/{total}][/cyan] ", end="")
            soundboard.play_sound(sound_name, blocking=True)
            idx += 1
    except KeyboardInterrupt:
        console.print("\n[yellow]⏸[/yellow] Queue playback interrupted.")
        soundboard.stop_sound()


@queue.command(name="skip")
def queue_skip() -> None:
    """Skip the next sound in the queue."""
    queue_mgr = QueueManager()
    skipped = queue_mgr.next()
    if skipped:
        console.print(f"[green]✓[/green] Skipped: {skipped}")
        console.print(f"[dim]Remaining: {queue_mgr.size()}[/dim]")
    else:
        console.print("[yellow]⚠[/yellow] Queue is empty")


@queue.command(name="shuffle")
def queue_shuffle() -> None:
    """Shuffle the queue."""
    queue_mgr = QueueManager()
    if queue_mgr.is_empty():
        console.print("[yellow]⚠[/yellow] Queue is empty")
        return
    queue_mgr.shuffle()
    console.print("[green]✓[/green] Queue shuffled")


# ─────────────────────────────────────────────────────────────────────────────
# Playlist Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group()
def playlist() -> None:
    """Manage saved playlists."""


@playlist.command(name="save")
@click.argument("name")
def playlist_save(name: str) -> None:
    """Save the current queue as a playlist.

    Example: muc playlist save gaming
    """
    queue_mgr = QueueManager()
    if queue_mgr.save_playlist(name):
        console.print(f"[green]✓[/green] Saved playlist '{name}' ({queue_mgr.size()} sounds)")
    else:
        console.print("[red]✗[/red] Cannot save empty queue as playlist")


@playlist.command(name="load")
@click.argument("name")
@click.option("--append", "-a", is_flag=True, help="Append to current queue instead of replacing")
def playlist_load(name: str, append: bool) -> None:
    """Load a playlist into the queue.

    Example: muc playlist load gaming
    """
    queue_mgr = QueueManager()
    if queue_mgr.load_playlist(name, append=append):
        action = "Appended" if append else "Loaded"
        console.print(f"[green]✓[/green] {action} playlist '{name}' ({queue_mgr.size()} sounds in queue)")
    else:
        console.print(f"[red]✗[/red] Playlist '{name}' not found")


@playlist.command(name="list")
def playlist_list() -> None:
    """Show all saved playlists."""
    queue_mgr = QueueManager()
    playlists = queue_mgr.list_playlists()

    if not playlists:
        console.print("[yellow]⚠[/yellow] No playlists saved. Use 'muc playlist save <name>' to create one.")
        return

    table = Table(title="Saved Playlists", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Sounds", style="cyan", justify="right")

    for name, count in sorted(playlists.items()):
        table.add_row(name, str(count))

    console.print(table)


@playlist.command(name="delete")
@click.argument("name")
def playlist_delete(name: str) -> None:
    """Delete a saved playlist.

    Example: muc playlist delete gaming
    """
    queue_mgr = QueueManager()
    if queue_mgr.delete_playlist(name):
        console.print(f"[green]✓[/green] Deleted playlist '{name}'")
    else:
        console.print(f"[red]✗[/red] Playlist '{name}' not found")


@playlist.command(name="show")
@click.argument("name")
def playlist_show(name: str) -> None:
    """Show contents of a playlist.

    Example: muc playlist show gaming
    """
    queue_mgr = QueueManager()
    sounds = queue_mgr.get_playlist(name)

    if sounds is None:
        console.print(f"[red]✗[/red] Playlist '{name}' not found")
        return

    table = Table(title=f"Playlist: {name}", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Sound Name", style="white")

    for idx, sound_name in enumerate(sounds, 1):
        table.add_row(str(idx), sound_name)

    console.print(table)


@cli.command()
def listen() -> None:
    """Start listening for hotkeys.

    Activates the soundboard to respond to hotkey presses.
    Uses both default (F1-F10) and custom hotkey bindings.
    Press ESC to stop listening.
    """
    soundboard, audio_manager = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    soundboard.setup_hotkeys()
    soundboard.list_hotkeys()

    # Get device name for status display
    device_name = "Not configured"
    if audio_manager.output_device_id is not None:
        try:
            device = sd.query_devices(audio_manager.output_device_id)
            device_name = str(device["name"])  # pyright: ignore[reportArgumentType, reportCallIssue]
        except (sd.PortAudioError, ValueError):
            pass

    # Create status display
    status = StatusDisplay(
        console=console,
        device_name=device_name,
        volume=audio_manager.volume,
        sound_count=len(soundboard.sounds),
        hotkey_count=len(soundboard.hotkeys),
    )

    # Hook into soundboard to update status
    original_play = soundboard.audio_manager.play_audio

    def play_with_status(
        audio_file: Path,
        *,
        blocking: bool = False,
        sound_volume: float = 1.0,
        show_progress: bool = True,
    ) -> bool:
        # Extract sound name from path
        sound_name = audio_file.stem
        status.update_playing(sound_name)
        result = original_play(
            audio_file,
            blocking=blocking,
            sound_volume=sound_volume,
            show_progress=show_progress,
        )
        status.update_stopped()
        return result

    soundboard.audio_manager.play_audio = play_with_status  # pyright: ignore[reportAttributeAccessIssue]

    console.print("\n[bold green]Soundboard Active![/bold green]")
    console.print("[dim]Press ESC to stop, or Ctrl+C to exit.[/dim]\n")

    soundboard.start_listening()
    status.start()

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
        status.stop()
        soundboard.stop_listening()
        # Restore original play_audio method
        soundboard.audio_manager.play_audio = original_play  # pyright: ignore[reportAttributeAccessIssue]
        console.print("\n[yellow]Stopped listening.[/yellow]")


@cli.command()
def stop() -> None:
    """Stop any currently playing sound."""
    soundboard, _ = get_soundboard()
    soundboard.stop_sound()
    console.print("[yellow]■[/yellow] Stopped current sound.")


@cli.command()
@click.argument("query", required=False)
def search(query: str | None) -> None:
    """Search for sounds by name with fuzzy matching.

    Supports fuzzy matching for typos and partial names.

    Examples:
        muc search air         # Find sounds containing 'air'
        muc search rickrol     # Fuzzy match for 'rickroll'

    """
    soundboard, _ = get_soundboard()
    metadata = MetadataManager()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        sys.exit(1)

    # If no query, prompt interactively
    if not query:
        query = str(click.prompt("Search for"))

    # Build tags dict
    tags = {name: metadata.get_metadata(name).tags for name in soundboard.sounds}

    results = search_sounds(query, soundboard.sounds, tags)

    if not results:
        console.print(f"[yellow]⚠[/yellow] No sounds matching '{query}'")
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

    console.print(table)

    # Offer to play
    if len(results) == 1:
        if click.confirm(f"Play '{results[0].name}'?"):
            soundboard.play_sound(results[0].name, blocking=True)
    elif click.confirm("Play a result?"):
        choice = click.prompt("Enter number", type=int, default=1)
        if 1 <= choice <= len(results):
            soundboard.play_sound(results[choice - 1].name, blocking=True)


@cli.command()
@click.argument("level", type=click.FloatRange(0.0, 1.0), required=False)
def volume(level: float | None) -> None:
    """Set or display the playback volume (0.0 to 1.0).

    Examples: mu volume 0.5 (set to 50%), mu volume (show current).
    """
    _, audio_manager = get_soundboard()
    if level is None:
        percentage = int(audio_manager.volume * 100)
        console.print(f"[cyan]Current volume:[/cyan] {percentage}%")
    else:
        audio_manager.set_volume(level)
        pm = ProfileManager()
        profile = pm.get_active_profile()
        profile.volume = audio_manager.volume
        pm.save_profile(profile)
        console.print("[green]✓[/green] Volume saved!")


@cli.command()
@click.option("--sequential", is_flag=True, help="Play sounds in alphabetical order instead of random.")
def auto(sequential: bool) -> None:
    """Play all sounds randomly, one after another.

    Each sound will play completely before the next one starts.
    Press Ctrl+C to stop playback.
    """
    soundboard, _ = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    with contextlib.suppress(KeyboardInterrupt):
        soundboard.play_all_sounds(shuffle=not sequential)


@cli.command()
def interactive() -> None:
    """Launch interactive menu mode.

    Provides a visual text-based menu for exploring and using the soundboard.
    Includes search, status display, and all soundboard features.
    """
    soundboard, audio_manager = get_soundboard()

    if not soundboard.sounds:
        console.print("[red]✗[/red] No sounds found.")
        console.print(f"[dim]Add audio files to: {soundboard.sounds_dir}[/dim]")
        sys.exit(1)

    soundboard.setup_hotkeys()

    # Use the enhanced interactive menu
    menu = InteractiveMenu(console, soundboard, audio_manager)
    menu.run()


# ─────────────────────────────────────────────────────────────────────────────
# Profile Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group()
def profile() -> None:
    """Manage configuration profiles.

    Profiles allow you to save different configurations for different
    games or scenarios (e.g., CS2, Battlefield, streaming).
    """


@profile.command(name="list")
def profile_list() -> None:
    """List all profiles.

    Shows all available profiles with their status and settings.
    """
    manager = ProfileManager()
    profiles = manager.list_profiles()
    active = manager.active_profile_name
    default = manager.default_profile_name

    table = Table(title="Configuration Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Display Name", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Device ID", justify="center")
    table.add_column("Volume", justify="center")

    for name in sorted(profiles):
        p = manager.get_profile(name)
        if not p:
            continue

        status = []
        if name == active:
            status.append("[green]ACTIVE[/green]")
        if name == default:
            status.append("[cyan]DEFAULT[/cyan]")
        status_str = " ".join(status) if status else "-"

        device_id = str(p.output_device_id) if p.output_device_id is not None else "-"
        volume_pct = f"{int(p.volume * 100)}%"

        table.add_row(name, p.display_name, status_str, device_id, volume_pct)

    console.print(table)


@profile.command(name="create")
@click.argument("name")
@click.option("--display", "-d", help="Display name for the profile")
@click.option("--description", help="Profile description")
@click.option("--copy", "-c", "copy_from", help="Copy settings from existing profile")
def profile_create(name: str, display: str | None, description: str | None, copy_from: str | None) -> None:
    """Create a new profile.

    Examples:
        muc profile create csgo
        muc profile create streaming --display "Streaming Mode"
        muc profile create bf2042 --copy csgo

    """
    manager = ProfileManager()

    try:
        p = manager.create_profile(
            name=name,
            display_name=display or "",
            description=description or "",
            copy_from=copy_from,
        )
        console.print(f"[green]✓[/green] Created profile: {p.display_name}")

        if click.confirm("Switch to this profile now?"):
            manager.switch_profile(name)
            console.print(f"[green]✓[/green] Switched to profile: {name}")

    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@profile.command(name="switch")
@click.argument("name")
def profile_switch(name: str) -> None:
    """Switch to a different profile.

    Example: muc profile switch csgo
    """
    manager = ProfileManager()
    p = manager.switch_profile(name)

    if p:
        console.print(f"[green]✓[/green] Switched to profile: {p.display_name}")
        console.print(f"[dim]Device: {p.output_device_id}, Volume: {int(p.volume * 100)}%[/dim]")
    else:
        console.print(f"[red]✗[/red] Profile '{name}' not found")
        console.print("[dim]Use 'muc profile list' to see available profiles[/dim]")
        sys.exit(1)


@profile.command(name="delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def profile_delete(name: str, force: bool) -> None:
    """Delete a profile.

    Example: muc profile delete old-profile
    """
    manager = ProfileManager()

    if not force and not click.confirm(f"Delete profile '{name}'?"):
        return

    try:
        if manager.delete_profile(name):
            console.print(f"[green]✓[/green] Deleted profile: {name}")
        else:
            console.print(f"[red]✗[/red] Profile '{name}' not found")
            sys.exit(1)
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@profile.command(name="show")
@click.argument("name", required=False)
def profile_show(name: str | None) -> None:
    """Show details of a profile.

    If no name provided, shows the active profile.

    Example: muc profile show csgo
    """
    manager = ProfileManager()

    if name is None:
        name = manager.active_profile_name

    p = manager.get_profile(name)
    if not p:
        console.print(f"[red]✗[/red] Profile '{name}' not found")
        sys.exit(1)

    info = f"""[bold cyan]{p.display_name}[/bold cyan] ({p.name})

[bold]Description:[/bold] {p.description or "None"}

[bold]Settings:[/bold]
├── Output Device ID: {p.output_device_id or "Not set"}
├── Volume: {int(p.volume * 100)}%
├── Sounds Directory: {p.sounds_dir or "Default"}
├── Sounds Directories: {len(p.sounds_dirs)} configured
└── Custom Hotkeys: {len(p.hotkeys)}

[bold]Timestamps:[/bold]
├── Created: {p.created_at.strftime("%Y-%m-%d %H:%M")}
└── Updated: {p.updated_at.strftime("%Y-%m-%d %H:%M")}"""

    console.print(Panel(info, title=f"Profile: {name}", border_style="cyan"))


@profile.command(name="set-default")
@click.argument("name")
def profile_set_default(name: str) -> None:
    """Set the default profile.

    Example: muc profile set-default csgo
    """
    manager = ProfileManager()

    if manager.set_default_profile(name):
        console.print(f"[green]✓[/green] Set '{name}' as default profile")
    else:
        console.print(f"[red]✗[/red] Profile '{name}' not found")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Config Export/Import Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group(name="config")
def config_group() -> None:
    """Manage configuration settings.

    Export and import configuration profiles to share with others or backup.
    """


@config_group.command(name="export")
@click.argument("output", type=click.Path())
@click.option("--profile", "-p", "profile_name", help="Profile to export (default: active)")
@click.option("--all", "export_all", is_flag=True, help="Export all profiles")
@click.option("--no-hotkeys", is_flag=True, help="Exclude hotkey bindings")
def config_export(output: str, profile_name: str | None, export_all: bool, no_hotkeys: bool) -> None:
    """Export configuration to a file.

    Examples:
        muc config export my-config.json
        muc config export backup.zip --all
        muc config export csgo.json --profile csgo

    """
    transfer = ConfigTransfer()
    output_path = Path(output)

    try:
        if export_all:
            result = transfer.export_all(output_path)
            console.print(f"[green]✓[/green] Exported all profiles to: {result}")
        else:
            name = profile_name or transfer.profile_manager.active_profile_name
            result = transfer.export_profile(
                name,
                output_path,
                include_hotkeys=not no_hotkeys,
            )
            console.print(f"[green]✓[/green] Exported profile '{name}' to: {result}")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@config_group.command(name="import")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--name", "-n", help="Import with different name")
@click.option("--overwrite", is_flag=True, help="Overwrite existing profile")
@click.option("--sounds-dir", type=click.Path(), help="Sounds directory to use")
def config_import(input_file: str, name: str | None, overwrite: bool, sounds_dir: str | None) -> None:
    """Import configuration from a file.

    Examples:
        muc config import my-config.json
        muc config import friend-config.json --name friend-settings
        muc config import backup.zip --overwrite

    """
    transfer = ConfigTransfer()
    input_path = Path(input_file)

    try:
        if input_path.suffix == ".zip":
            imported = transfer.import_all(input_path, overwrite=overwrite)
            console.print(f"[green]✓[/green] Imported {len(imported)} profiles: {', '.join(imported)}")
        else:
            p = transfer.import_profile(
                input_path,
                new_name=name,
                overwrite=overwrite,
                sounds_dir=Path(sounds_dir) if sounds_dir else None,
            )
            console.print(f"[green]✓[/green] Imported profile: {p.display_name}")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Sounds Directories Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group(name="dirs")
def directories() -> None:
    """Manage sounds directories.

    Configure multiple directories to load sounds from.
    Sounds from later directories override earlier ones with the same name.
    """


@directories.command(name="list")
def dirs_list() -> None:
    """List all configured sounds directories."""
    pm = ProfileManager()
    p = pm.get_active_profile()

    dirs = p.sounds_dirs
    if not dirs and p.sounds_dir:
        dirs = [p.sounds_dir]

    manager = SoundsDirectoryManager([Path(d) for d in dirs])
    manager.list_directories(console)


@directories.command(name="add")
@click.argument("path", type=click.Path())
def dirs_add(path: str) -> None:
    """Add a sounds directory.

    Example: muc dirs add ~/more-sounds
    """
    pm = ProfileManager()
    p = pm.get_active_profile()

    path_obj = Path(path).resolve()

    dirs = list(p.sounds_dirs)
    if not dirs and p.sounds_dir:
        dirs = [p.sounds_dir]

    if str(path_obj) in dirs:
        console.print(f"[yellow]⚠[/yellow] Directory already configured: {path_obj}")
        return

    if not path_obj.exists():
        if click.confirm("Directory doesn't exist. Create it?"):
            path_obj.mkdir(parents=True, exist_ok=True)
        else:
            return

    dirs.append(str(path_obj))
    p.sounds_dirs = dirs
    pm.save_profile(p)

    console.print(f"[green]✓[/green] Added directory: {path_obj}")


@directories.command(name="remove")
@click.argument("path", type=click.Path())
def dirs_remove(path: str) -> None:
    """Remove a sounds directory.

    Example: muc dirs remove ~/old-sounds
    """
    pm = ProfileManager()
    p = pm.get_active_profile()

    path_obj = Path(path).resolve()

    dirs = list(p.sounds_dirs)
    if not dirs:
        console.print("[yellow]⚠[/yellow] No directories configured")
        return

    if str(path_obj) not in dirs:
        console.print(f"[yellow]⚠[/yellow] Directory not configured: {path_obj}")
        return

    dirs.remove(str(path_obj))
    p.sounds_dirs = dirs
    pm.save_profile(p)

    console.print(f"[green]✓[/green] Removed directory: {path_obj}")


@directories.command(name="conflicts")
def dirs_conflicts() -> None:
    """Show sound name conflicts across directories.

    When the same sound name exists in multiple directories,
    the sound from the last directory in the list is used.
    """
    pm = ProfileManager()
    p = pm.get_active_profile()

    dirs = p.sounds_dirs
    if not dirs and p.sounds_dir:
        dirs = [p.sounds_dir]

    manager = SoundsDirectoryManager([Path(d) for d in dirs])
    manager.show_conflicts(console)


# ─────────────────────────────────────────────────────────────────────────────
# Download & Audio Management Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("url")
@click.option("--name", "-n", help="Output filename (without extension)")
@click.option("--start", "-s", help="Start time (e.g., '0:30' or '30')")
@click.option("--end", "-e", help="End time (e.g., '1:00' or '60')")
@click.option(
    "--format",
    "-f",
    "audio_format",
    default="wav",
    type=click.Choice(["wav", "mp3", "ogg"]),
    help="Output audio format",
)
def download(url: str, name: str | None, start: str | None, end: str | None, audio_format: str) -> None:
    """Download audio from YouTube.

    Downloads the audio track from a YouTube video and saves it
    to your sounds directory.

    Examples:
        muc download "https://youtube.com/watch?v=..." --name my-sound
        muc download "https://youtu.be/..." --start 0:15 --end 0:30
        muc download "https://youtube.com/..." --format mp3

    """
    if not check_yt_dlp_available():
        console.print("[red]✗[/red] yt-dlp is not installed")
        console.print("\n[dim]Install with:[/dim]")
        console.print("  uv add yt-dlp")
        console.print("  [dim]or[/dim]")
        console.print("  pip install yt-dlp")
        sys.exit(1)

    if not check_ffmpeg_available():
        console.print("[red]✗[/red] ffmpeg is not installed (required for audio conversion)")
        console.print("[dim]Download from: https://ffmpeg.org/download.html[/dim]")
        sys.exit(1)

    # Get sounds directory from profile
    pm = ProfileManager()
    profile = pm.get_active_profile()

    sounds_dirs = profile.sounds_dirs
    if sounds_dirs:
        sounds_dir = Path(sounds_dirs[0])  # Use first directory
    elif profile.sounds_dir:
        sounds_dir = Path(profile.sounds_dir)
    else:
        sounds_dir = Path.cwd() / "sounds"

    downloader = YouTubeDownloader(console, sounds_dir)

    # Validate URL
    video_id = downloader.validate_url(url)
    if not video_id:
        console.print("[red]✗[/red] Invalid YouTube URL")
        console.print("[dim]Supported formats: youtube.com/watch?v=..., youtu.be/...[/dim]")
        sys.exit(1)

    # Get video info
    console.print("[dim]Fetching video information...[/dim]")
    info = downloader.get_video_info(url)

    if info:
        duration = info.get("duration")
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
        console.print(f"\n[bold]{info['title']}[/bold]")
        console.print(f"[dim]Duration: {duration_str} | By: {info.get('uploader', 'Unknown')}[/dim]\n")

    # Download with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=100)

        def update_progress(percent: float, status: str) -> None:
            progress.update(task, completed=percent, description=status)

        result = downloader.download(
            url=url,
            output_name=name,
            start_time=start,
            end_time=end,
            audio_format=audio_format,
            progress_callback=update_progress,
        )

    if result:
        console.print(f"\n[green]✓[/green] Downloaded: [bold]{result.name}[/bold]")
        console.print(f"[dim]Saved to: {result}[/dim]")

        # Offer to play
        if click.confirm("Play the downloaded sound?"):
            soundboard, _ = get_soundboard()
            soundboard.play_sound(result.stem, blocking=True)
    else:
        console.print("[red]✗[/red] Download failed")
        sys.exit(1)


@cli.command()
@click.argument("sound_name")
@click.option("--start", "-s", default="0", help="Start time (e.g., '0:30')")
@click.option("--end", "-e", help="End time (e.g., '1:00')")
@click.option("--output", "-o", help="Output filename")
@click.option("--fade-in", type=float, default=0, help="Fade in duration (seconds)")
@click.option("--fade-out", type=float, default=0, help="Fade out duration (seconds)")
@click.option("--preview", "-p", is_flag=True, help="Preview before saving")
def trim(
    sound_name: str,
    start: str,
    end: str | None,
    output: str | None,
    fade_in: float,
    fade_out: float,
    preview: bool,
) -> None:
    """Trim an audio file to a specific time range.

    Creates a new file, preserving the original.

    Examples:
        muc trim airhorn --start 0:00 --end 0:05
        muc trim long_song --start 1:30 --end 2:00 --output chorus
        muc trim intro --end 5 --fade-out 0.5

    """
    soundboard, audio_manager = get_soundboard()

    if sound_name not in soundboard.sounds:
        console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
        sys.exit(1)

    input_path = soundboard.sounds[sound_name]
    trimmer = AudioTrimmer()

    # Parse times
    start_secs = trimmer.parse_time_to_seconds(start)
    end_secs = trimmer.parse_time_to_seconds(end) if end else None

    # Get original duration
    original_duration = trimmer.get_duration(input_path)

    # Validate
    if end_secs and end_secs > original_duration:
        console.print(f"[yellow]⚠[/yellow] End time exceeds duration ({original_duration:.1f}s), will use end of file")
        end_secs = original_duration

    # Calculate new duration
    new_duration = (end_secs or original_duration) - start_secs

    # Show info
    console.print(f"\n[bold]Trimming: {sound_name}[/bold]")
    console.print(f"Original: {trimmer.format_seconds(original_duration)}")
    console.print(
        f"New: {trimmer.format_seconds(start_secs)} → "
        f"{trimmer.format_seconds(end_secs or original_duration)} ({trimmer.format_seconds(new_duration)})",
    )

    if fade_in:
        console.print(f"Fade in: {fade_in}s")
    if fade_out:
        console.print(f"Fade out: {fade_out}s")

    # Preview
    if preview:
        console.print("\n[dim]Playing preview of original audio...[/dim]")
        soundboard.play_sound(sound_name, blocking=True)

    # Confirm
    if not click.confirm("\nProceed with trim?", default=True):
        return

    # Determine output path
    output_path = input_path.parent / f"{output}{input_path.suffix}" if output else None

    # Trim
    try:
        result = trimmer.trim(
            input_path=input_path,
            output_path=output_path,
            start=start_secs,
            end=end_secs,
            fade_in=fade_in,
            fade_out=fade_out,
        )

        console.print(f"\n[green]✓[/green] Created: [bold]{result.name}[/bold]")
        console.print(f"[dim]Duration: {trimmer.format_seconds(new_duration)}[/dim]")

        # Offer to play
        if click.confirm("Play the trimmed sound?"):
            audio_manager.play_audio(result, blocking=True)

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗[/red] Trim failed: {e}")
        sys.exit(1)


@cli.command(name="normalize")
@click.argument("sound_name", required=False)
@click.option("--all", "normalize_all", is_flag=True, help="Normalize all sounds")
@click.option("--target", "-t", type=float, default=-3.0, help="Target level in dB (default: -3)")
@click.option("--mode", type=click.Choice(["peak", "rms"]), default="peak", help="Normalization mode")
@click.option("--in-place", is_flag=True, help="Overwrite original files")
@click.option("--analyze", "-a", is_flag=True, help="Only analyze, don't normalize")
def normalize_cmd(
    sound_name: str | None,
    normalize_all: bool,
    target: float,
    mode: str,
    in_place: bool,
    analyze: bool,
) -> None:
    """Normalize audio levels.

    Adjusts volume to a consistent level across sounds.

    Examples:
        muc normalize airhorn                    # Normalize single sound
        muc normalize --all                      # Normalize all sounds
        muc normalize airhorn --target -6        # Target -6 dB
        muc normalize airhorn --analyze          # Just show levels
        muc normalize --all --in-place           # Overwrite originals

    """
    soundboard, _ = get_soundboard()
    normalizer = AudioNormalizer()

    # Determine files to process
    if normalize_all:
        files = list(soundboard.sounds.values())
    elif sound_name:
        if sound_name not in soundboard.sounds:
            console.print(f"[red]✗[/red] Sound '{sound_name}' not found")
            sys.exit(1)
        files = [soundboard.sounds[sound_name]]
    else:
        console.print("[red]✗[/red] Specify a sound name or use --all")
        sys.exit(1)

    if not files:
        console.print("[yellow]⚠[/yellow] No sounds to process")
        return

    # Analyze mode
    if analyze:
        table = Table(title="Audio Level Analysis", show_header=True)
        table.add_column("Sound", style="white")
        table.add_column("Peak (dB)", justify="right")
        table.add_column("RMS (dB)", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Status", justify="center")

        for file_path in files:
            info = normalizer.analyze(file_path)

            # Determine status
            if info["peak_db"] > -1:
                status = "[red]CLIPPING[/red]"
            elif info["peak_db"] < -12:
                status = "[yellow]QUIET[/yellow]"
            else:
                status = "[green]OK[/green]"

            table.add_row(
                file_path.stem,
                f"{info['peak_db']:.1f}",
                f"{info['rms_db']:.1f}",
                f"{info['duration']:.1f}s",
                status,
            )

        console.print(table)
        return

    # Normalize
    if in_place and not click.confirm("This will overwrite original files. Continue?"):
        return

    console.print(f"\n[cyan]Normalizing {len(files)} file(s) to {target} dB ({mode} mode)...[/cyan]\n")

    with Progress(console=console) as progress:
        task = progress.add_task("Normalizing...", total=len(files))

        def update(current: int, name: str) -> None:
            progress.update(task, completed=current, description=f"Processing: {name}")

        results = normalizer.normalize_batch(
            files,
            target_db=target,
            mode=mode,
            in_place=in_place,
            progress_callback=update,
        )

    console.print(f"\n[green]✓[/green] Normalized {len(results)} file(s)")

    if not in_place:
        console.print("[dim]Original files preserved. New files have '_normalized' suffix.[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Cache Management Commands
# ─────────────────────────────────────────────────────────────────────────────


@cli.group()
def cache() -> None:
    """Manage the audio cache.

    The cache stores recently played sounds in memory for faster playback.
    """


@cache.command(name="stats")
def cache_stats() -> None:
    """Show cache statistics.

    Displays information about cache usage, hit rate, and memory consumption.
    """
    _, audio_manager = get_soundboard()
    stats = audio_manager.cache_stats

    table = Table(title="Audio Cache Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="cyan", justify="right")

    table.add_row("Cached Sounds", str(stats["entries"]))
    table.add_row("Cache Size", f"{stats['size_mb']:.1f} MB")
    table.add_row("Max Size", f"{stats['max_size_mb']:.1f} MB")
    table.add_row("Cache Hits", str(stats["hits"]))
    table.add_row("Cache Misses", str(stats["misses"]))
    table.add_row("Hit Rate", f"{stats['hit_rate_percent']:.1f}%")

    console.print(table)

    if not audio_manager.cache_enabled:
        console.print("\n[yellow]⚠[/yellow] Cache is currently disabled")


@cache.command(name="clear")
def cache_clear() -> None:
    """Clear the audio cache.

    Removes all cached sounds from memory.
    """
    _, audio_manager = get_soundboard()
    audio_manager.clear_cache()


@cache.command(name="preload")
@click.option("--hotkeys", "-h", is_flag=True, help="Preload sounds bound to hotkeys")
@click.option("--favorites", "-f", is_flag=True, help="Preload favorite sounds")
@click.option("--all", "preload_all", is_flag=True, help="Preload all sounds")
def cache_preload(hotkeys: bool, favorites: bool, preload_all: bool) -> None:
    """Pre-load sounds into cache for faster playback.

    Examples:
        muc cache preload --hotkeys     # Preload hotkey sounds
        muc cache preload --favorites   # Preload favorites
        muc cache preload --all         # Preload all sounds

    """
    soundboard, audio_manager = get_soundboard()
    metadata = MetadataManager()

    if not audio_manager.cache_enabled:
        console.print("[yellow]⚠[/yellow] Cache is disabled. Enable with 'muc cache enable'")
        return

    paths: list[Path] = []

    if preload_all:
        paths = list(soundboard.sounds.values())
    else:
        if hotkeys:
            soundboard.setup_hotkeys()
            for sound_name in soundboard.hotkeys.values():
                if sound_name in soundboard.sounds:
                    paths.append(soundboard.sounds[sound_name])

        if favorites:
            for name in soundboard.sounds:
                if metadata.get_metadata(name).favorite:
                    paths.append(soundboard.sounds[name])

    if not paths:
        console.print("[yellow]⚠[/yellow] No sounds to preload. Use --hotkeys, --favorites, or --all")
        return

    # Remove duplicates
    paths = list(set(paths))

    console.print(f"[cyan]Preloading {len(paths)} sounds...[/cyan]")
    loaded = audio_manager.preload_sounds(paths)
    console.print(f"[green]✓[/green] Preloaded {loaded} sounds into cache")


@cache.command(name="enable")
def cache_enable() -> None:
    """Enable the audio cache."""
    _, audio_manager = get_soundboard()
    audio_manager.set_cache_enabled(True)
    console.print("[green]✓[/green] Audio cache enabled")


@cache.command(name="disable")
def cache_disable() -> None:
    """Disable the audio cache."""
    _, audio_manager = get_soundboard()
    audio_manager.set_cache_enabled(False)
    console.print("[green]✓[/green] Audio cache disabled")


@cache.command(name="size")
@click.argument("size_mb", type=int)
def cache_set_size(size_mb: int) -> None:
    """Set the maximum cache size in MB.

    Example: muc cache size 200
    """
    if size_mb < 1:
        console.print("[red]✗[/red] Cache size must be at least 1 MB")
        sys.exit(1)

    _, audio_manager = get_soundboard()
    audio_manager.set_cache_size(size_mb)
    console.print(f"[green]✓[/green] Cache size set to {size_mb} MB")


def main() -> None:
    """Entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)
    except MUCError as e:
        console.print(f"\n[red]✗[/red] {e.message}")
        console.print(f"[dim]💡 {e.suggestion}[/dim]")
        console.print(f"\n[dim]Error code: E{e.code} | Run with --debug for more details[/dim]")
        sys.exit(1)
    except (OSError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
