# MUC Soundboard 🎵🎮

Play audio files through your microphone in multiplayer games like CS, Battlefield, and COD using hotkeys. Built with Python and Rich for a beautiful CLI experience!

## ✨ Features

- 🎵 **Play audio through your mic** - Route sound to your virtual microphone
- ⌨️ **Custom hotkeys** - Bind any key combination to any sound (F1-F12, Ctrl+, Alt+, etc.)
- 🏷️ **Tags & categories** - Organize sounds with tags and filter by category
- ⭐ **Favorites** - Mark and quickly access your most-used sounds
- 🔊 **Per-sound volume** - Set individual volume levels (0-200%) for each sound
- 📋 **Queue & playlists** - Build queues and save them as reusable playlists
- 🎨 **Beautiful CLI** - Rich-click powered interface with colors and tables
- 📊 **Progress bar** - Visual playback progress with time display
- 🎛️ **Multiple formats** - Supports WAV, MP3, OGG, FLAC, M4A
- 🔍 **Auto-detection** - Finds VB-Cable and virtual audio devices automatically
- 🔎 **Fuzzy search** - Find sounds quickly with typo-tolerant search
- 📁 **Organized library** - Subdirectory support for sound organization
- 🔉 **Global volume** - Adjustable playback volume with persistent settings
- 🎲 **Auto-play mode** - Play all sounds randomly or sequentially
- 📥 **YouTube download** - Download audio directly from YouTube with yt-dlp
- ✂️ **Audio trimming** - Trim sounds with optional fade in/out
- 🔊 **Audio normalization** - Normalize levels for consistent volume
- ⚙️ **Persistent config** - Saves your settings to `~/.muc/config.json`
- 👤 **Configuration profiles** - Create and switch between different setups for different games
- 📤 **Config export/import** - Share configurations between machines or with friends
- 📂 **Multiple sounds directories** - Scan sounds from multiple folders with override support
- ⚡ **Performance optimized** - LRU audio cache for instant playback, lazy loading for fast startup
- 🧠 **Memory management** - Configurable cache size with automatic eviction
- 🎮 **Gaming ready** - Perfect for CS, Battlefield, COD, and more!

## 📋 Prerequisites

### 1. Python Environment
- **Python 3.13** or higher
- **uv** or **pip** for package management

### 2. Virtual Audio Cable
**CRITICAL**: You need a virtual audio device to route audio to your microphone.

**Recommended: VB-Cable (Free)**
1. Download from: https://vb-audio.com/Cable/
2. Install the driver with admin privilege
3. Restart your computer (required!)
4. This creates:
   - `CABLE Input` - Where your soundboard outputs audio
   - `CABLE Output` - What your game reads as a microphone

**NOTE**: This will switch your default audio and microphone devices to VB-Cable. Revert them back to your real devices.

## 🚀 Installation

### Quick Start

1. **Install via uv or pip:**
   ```bash
   uv add muc
   # optional: with yt-dlp for downloading audio
   uv add muc[yt-dlp]
   ```

2. **Add your audio files:**
   - Place audio files (MP3, WAV, OGG, FLAC, M4A) in the `sounds/` directory
   - Organize in subdirectories if desired
   - The app automatically scans and loads all audio files

## ⚙️ Setup

### Step 1: Configure VB-Cable

**In Windows Sound Settings:**
1. Right-click speaker icon in taskbar → **Sound settings**
2. Under **Input**, select your real microphone (HyperX, Blue Yeti, etc.)
3. This is for your actual voice

**In Your Game Settings:**
1. Open game audio/voice settings
2. Set **Input Device** to: `CABLE Output (VB-Audio Virtual Cable)`
3. Your teammates will now hear audio from the soundboard + your voice (if using software mixing)

### Step 2: Run Setup Wizard

```bash
muc setup
```

The setup wizard will:
1. 📋 List all available audio devices in a beautiful table
2. 🔍 Auto-detect VB-Cable or similar virtual devices
3. ✓ Let you confirm or manually select the output device
4. 💾 Save your configuration to `~/.muc/config.json`

**IMPORTANT**: Select `CABLE Input` as the output device, not `CABLE Output`.

```
CABLE Input  ← Soundboard outputs HERE
     ↓
CABLE Output ← Game reads FROM here
```

## 🎮 Usage

### CLI Commands

MUC provides a modern CLI with multiple commands:

```bash
# Setup and configuration
muc setup          # Run setup wizard
muc devices        # List all audio devices

# Sound management
muc sounds         # List available sounds in your library
muc sounds --tag meme        # Filter by tag
muc sounds --favorites       # Show only favorites
muc search [query] # Fuzzy search for sounds by name or tag
muc play [name]    # Play a specific sound (prompts if no name)
muc stop           # Stop currently playing sound
muc auto           # Play all sounds randomly (use --sequential for alphabetical order)
muc info [name]    # Show detailed info about a sound

# Tags & organization
muc tag airhorn meme loud    # Add tags to a sound
muc untag airhorn loud       # Remove tags from a sound
muc tags                     # List all tags with counts

# Favorites
muc favorite airhorn         # Toggle favorite status
muc favorite airhorn --on    # Add to favorites
muc favorites                # List all favorites

# Volume control
muc volume         # Show current global volume
muc volume 0.5     # Set global volume to 50% (0.0 to 1.0)
muc sound-volume airhorn 1.5   # Set per-sound volume to 150% (0.0 to 2.0)

# Custom hotkeys
muc bind f1 airhorn          # Bind F1 to play airhorn
muc bind "<ctrl>+a" applause # Bind Ctrl+A to applause
muc unbind f1                # Remove hotkey binding
muc unbind airhorn           # Remove all bindings for a sound
muc hotkeys                  # Show all hotkey bindings
muc hotkeys-reset            # Reset to default F1-F10 bindings
muc listen                   # Start hotkey listener (press ESC to stop)

# Queue management
muc queue add airhorn explosion  # Add sounds to queue
muc queue show               # Show current queue
muc queue play               # Play queue sequentially
muc queue skip               # Skip to next sound
muc queue shuffle            # Shuffle the queue
muc queue clear              # Clear the queue

# Playlists
muc playlist save mylist     # Save current queue as playlist
muc playlist load mylist     # Load playlist into queue
muc playlist list            # List all saved playlists
muc playlist show mylist     # Show playlist contents
muc playlist delete mylist   # Delete a playlist

# Configuration profiles
muc profile list             # List all profiles
muc profile show [name]      # Show profile details
muc profile create <name>    # Create a new profile
muc profile switch <name>    # Switch to a different profile
muc profile delete <name>    # Delete a profile
muc profile clone <src> <new> # Clone an existing profile

# Config export/import
muc config export <file>     # Export current profile to JSON
muc config import <file>     # Import profile from JSON
muc config export-all <file> # Export all profiles to ZIP archive

# Multiple sounds directories
muc dirs list                # List configured sounds directories
muc dirs add <path>          # Add a sounds directory
muc dirs remove <path>       # Remove a sounds directory
muc dirs conflicts           # Show sounds with name conflicts

# Download & audio tools
muc download <url>           # Download audio from YouTube
muc download <url> --name myfile --start 0:15 --end 0:30  # With trim
muc trim <sound> --start 0:00 --end 0:05   # Trim audio file
muc normalize <sound>        # Normalize audio levels
muc normalize --all          # Normalize all sounds
muc normalize --analyze      # Just analyze levels

# Cache management (performance)
muc cache stats              # Show cache statistics (hits, size, hit rate)
muc cache clear              # Clear the audio cache
muc cache preload --hotkeys  # Pre-load sounds bound to hotkeys
muc cache preload --favorites # Pre-load favorite sounds
muc cache preload --all      # Pre-load all sounds
muc cache enable             # Enable audio caching
muc cache disable            # Disable audio caching
muc cache size 200           # Set max cache size to 200 MB

# Memory management
muc memory stats             # Show memory usage statistics
muc memory cleanup           # Force garbage collection
muc memory cleanup --aggressive  # Also clear cache

# Interactive mode
muc interactive    # Launch full interactive menu

# Help
muc --help         # Show all commands
```

### Quick Workflow

1. **First time setup:**
   ```bash
   muc setup
   ```

2. **Check your sounds:**
   ```bash
   muc sounds
   ```

3. **Test a sound:**
   ```bash
   muc play rickroll
   ```

4. **Start gaming with hotkeys:**
   ```bash
   muc listen
   ```
   - Press F1-F10 to play sounds
   - Press ESC to stop

### Hotkey Bindings

By default, the first 10 sounds (alphabetically) are mapped to F1-F10.

**Custom hotkeys** let you bind any key combination:
```bash
muc bind f1 airhorn              # Simple key
muc bind "<ctrl>+<shift>+a" boom # Modifier keys
muc bind "<alt>+1" explosion     # Alt + number
```

**Hotkey modes** (set in config):
- `default` - Only use auto-assigned F1-F10
- `custom` - Only use your custom bindings
- `merged` - Use both (default)

View bindings:
```bash
muc hotkeys
```

Reset to defaults:
```bash
muc hotkeys-reset
```

### Interactive Menu Mode

For a full-featured visual menu:
```bash
muc interactive
```

Features a visual status header showing device, volume, and sound count, plus:
- 🎵 List & play sounds
- 🔍 Search sounds (fuzzy matching)
- ⌨️ View & manage hotkeys
- 🎧 Start hotkey listener
- ⏹️ Stop current sound
- 🔊 Adjust volume
- ⚙️ Change output device
- 🎲 Auto-play all sounds

## 🎵 Audio File Management

### Supported Formats
- **WAV** - Best quality, larger files
- **MP3** - Good quality, smaller files
- **OGG** - Good quality, open format
- **FLAC** - Lossless quality, large files
- **M4A** - Apple format

### Directory Organization

```
sounds/
├── music/
│   ├── song1.mp3
│   └── song2.mp3
├── effects/
│   ├── airhorn.wav
│   └── explosion.wav
├── memes/
│   └── rickroll.mp3
└── random_sound.mp3
```

The app recursively scans all subdirectories.

### Recommendations

- **Sample Rate**: 48000 Hz
- **Bit Depth**: 16-bit (WAV)
- **Bitrate**: 192-320 kbps (MP3)
- **Length**: Under 30 seconds for best performance
- **Volume**: Normalize audio to -3dB to prevent clipping
- **Naming**: Use descriptive names without special characters

### Getting Audio Files

**Using built-in downloader (recommended):**
```bash
# Download from YouTube directly to your sounds folder
muc download "https://youtube.com/watch?v=..." --name my-sound

# Download with time range extraction
muc download "https://youtube.com/..." --start 0:15 --end 0:45

# Choose output format
muc download "https://youtu.be/..." --format mp3
```

**Requirements for download command:**
- yt-dlp: `uv add muc[yt-dlp]` or `pip install yt-dlp`
- ffmpeg: Download from https://ffmpeg.org/download.html

**Manual method:**
```bash
# Download using yt-dlp directly
yt-dlp -x --audio-format wav "https://youtube.com/watch?v=..."

# Move file to sounds/
mv video.wav sounds/
```

### Audio Processing

**Trim sounds:**
```bash
# Trim to specific time range
muc trim airhorn --start 0:00 --end 0:05

# Trim with fade effects
muc trim long_song --start 1:30 --end 2:00 --fade-in 0.5 --fade-out 0.5

# Save with custom name
muc trim intro --end 10 --output short_intro
```

**Normalize audio levels:**
```bash
# Normalize a single sound
muc normalize airhorn

# Analyze levels without changing
muc normalize --all --analyze

# Normalize all sounds to -6 dB
muc normalize --all --target -6

# Use RMS normalization (loudness-based)
muc normalize airhorn --mode rms
```

## ⚡ Performance Optimization

MUC includes built-in performance optimizations for low-latency playback:

### Audio Caching

Frequently played sounds are cached in memory for instant playback:

```bash
# View cache statistics
muc cache stats

# Pre-load hotkey sounds for zero-latency playback
muc cache preload --hotkeys

# Pre-load all favorites
muc cache preload --favorites

# Adjust cache size (default: 100 MB)
muc cache size 200
```

**Cache benefits:**
- **First playback**: ~100ms (loads from disk)
- **Cached playback**: <20ms (from memory)
- **Hit rate**: Typically >80% for repeated sounds

### Memory Management

Monitor and control memory usage:

```bash
# Check memory statistics
muc memory stats

# Free unused memory
muc memory cleanup

# Aggressive cleanup (also clears cache)
muc memory cleanup --aggressive
```

**Memory limits:**
- Default cache: 100 MB
- LRU eviction: Least recently used sounds are automatically removed
- Configurable: Adjust based on your system's RAM

## 🔧 Configuration

Configuration is stored in `~/.muc/` with support for multiple profiles:

```
~/.muc/
├── config.json          # Global settings (active profile, default profile)
├── profiles/
│   ├── default.json     # Default profile
│   ├── csgo.json        # Game-specific profile
│   └── streaming.json   # Custom profile
├── metadata.json        # Sound tags, favorites, volumes, play counts
└── playlists.json       # Saved playlists
```

### Profile Settings

Each profile contains:
```json
{
  "name": "csgo",
  "display_name": "CS:GO Competitive",
  "description": "Settings for CS:GO matches",
  "settings": {
    "output_device_id": 6,
    "sounds_dir": "C:/path/to/sounds",
    "sounds_dirs": ["C:/sounds/main", "C:/sounds/memes"],
    "volume": 0.8,
    "hotkeys": {
      "<f1>": "airhorn",
      "<ctrl>+<shift>+a": "applause"
    },
    "hotkey_mode": "merged"
  }
}
```

### Profile Workflow

```bash
# Create profiles for different games
muc profile create "CS:GO" --description "Counter-Strike settings"
muc profile create "Valorant" --copy-from csgo

# Switch between profiles
muc profile switch csgo
muc profile switch valorant

# Export/import for backup or sharing
muc config export csgo-settings.json
muc config import csgo-settings.json --name "imported-csgo"
muc config export-all full-backup.zip
```

### Multiple Sounds Directories

You can configure multiple directories to scan for sounds:

```bash
# Add directories (later directories override earlier ones for same-named sounds)
muc dirs add "C:/sounds/main"
muc dirs add "C:/sounds/game-specific"
muc dirs add "D:/shared-sounds"

# View configured directories
muc dirs list

# Check for naming conflicts
muc dirs conflicts
```

This is useful for:
- Keeping a base sound library + game-specific overrides
- Sharing sounds across multiple profiles
- Organizing sounds by category in different folders

## 🎯 Gaming Tips

1. **Test First**: Always test sounds before joining a match
   ```bash
   muc play test-sound
   ```

2. **Volume Control**:
   - Use `muc volume 0.5` to set soundboard volume to 50%
   - Use audio editing software to normalize clips
   - Set in-game voice volume appropriately

3. **Quick Access**:
   - Keep a terminal with `muc listen` running
   - Alt-tab is instant with hotkeys
   - Or use a second monitor

4. **Push-to-Talk**:
   - If your game uses PTT, you'll need to hold it while playing sounds
   - Or configure the game to use voice activation

5. **Be Respectful**:
   - Don't spam sounds excessively
   - Use appropriate audio in competitive matches
   - Some communities have rules about soundboards

## 🐛 Troubleshooting

### "No virtual audio cable detected"
**Solution**: Install VB-Cable and **restart your computer**
```bash
muc setup  # Run again after restart
```

### "Teammates can't hear the audio"
**Check**:
1. Game microphone set to `CABLE Output` ✓
2. Soundboard output set to `CABLE Input` ✓
3. Test with: `muc play test-sound`

**Fix**:
```bash
muc devices  # Verify device IDs
muc setup    # Reconfigure if needed
```

### "Audio plays on my speakers, not through mic"
**Problem**: Wrong output device selected

**Solution**:
```bash
muc devices  # Find CABLE Input ID
muc setup    # Select correct device
```

Remember: **CABLE Input** (not Output) for soundboard output!

### "Hotkeys don't work"
**Causes**:
- Windows blocking global hotkeys
- Another app using same keys
- Listener not started

**Solutions**:
```bash
# Run as administrator (Windows)
# Or try interactive mode
muc interactive  # Then select option 4
```

### "Audio quality is poor"
**Improve quality**:
1. Use WAV or high-bitrate MP3 files
2. Match sample rate to your device (usually 48000 Hz)
3. Normalize audio levels
4. Check VB-Cable settings in Windows Sound Control Panel

### "Configuration not saving"
**Check**: Permissions for `~/.muc/` directory

```powershell
# Windows - check directory
ls ~\.muc

# If missing, create manually
mkdir ~\.muc
```

## 🏗️ Architecture

This project implements a clean software architecture:

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                        │
│            Rich-click commands (cli.py)             │
└───────────────────────┬─────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬─────────────┐
        │               │               │             │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐ ┌───▼───────────┐
│Profile Manager│ │  Metadata │ │ Queue Manager │ │Config Transfer│
│  (profiles)   │ │(tags,favs)│ │ (playlists)   │ │(export/import)│
└───────┬───────┘ └─────┬─────┘ └───────┬───────┘ └───────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                   Soundboard                        │
│     (sound library, hotkey manager, playback)       │
│              + SoundsDirectoryManager               │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                  Audio Manager                      │
│           (devices, volume, playback)               │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Virtual Audio Device                   │
│              (VB-Cable, etc.)                       │
└─────────────────────────────────────────────────────┘
```

**Flow**:
1. User runs command → CLI parses → Config loads settings
2. Soundboard scans sounds → Loads metadata (tags, volumes)
3. HotkeyManager sets up bindings (default + custom)
4. User presses hotkey → Handler triggered → Metadata volume applied
5. Audio Manager loads file → Outputs to virtual device
6. Game reads from virtual device → Teammates hear sound

## 📁 Project Structure

```
muc/
├── src/
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # Rich-click CLI commands
│   ├── config.py            # Configuration management
│   ├── profile_manager.py   # Configuration profiles
│   ├── config_transfer.py   # Export/import configurations
│   ├── sounds_directories.py # Multiple sounds directories
│   ├── audio_manager.py     # Audio device & playback
│   ├── soundboard.py        # Sound library & hotkeys
│   ├── metadata.py          # Tags, favorites, per-sound volume
│   ├── hotkey_manager.py    # Custom hotkey bindings
│   ├── queue_manager.py     # Queue & playlist management
│   ├── validators.py        # Input validation
│   ├── exceptions.py        # Custom exceptions
│   └── logging_config.py    # Logging setup
├── sounds/                  # Audio files directory
│   └── README.md            # Sound library guide
├── tests/                   # Unit & integration tests
├── pyproject.toml           # Project metadata & dependencies
├── README.md                # This file
└── Makefile                 # Development commands
```

## 🤝 Contributing

This is a personal project, but contributions are welcome!

**Ways to contribute**:
- 🐛 Report bugs or issues
- 💡 Suggest new features
- 🎵 Share cool sound packs
- 📖 Improve documentation
- 🔧 Submit pull requests

## ⚖️ Legal & Ethics

**Usage Guidelines**:
- ✓ Personal use and education
- ✓ Private games with friends
- ✗ Harassment or abuse
- ✗ Circumventing game rules
- ✗ Competitive advantage in ranked games

**Copyright**:
- Ensure you have rights to audio files
- Respect copyright and fair use
- Don't distribute copyrighted content

**Game ToS**:
- Check your game's terms of service
- Some games prohibit audio injection
- Use responsibly to avoid bans

## 📄 License

This project is provided as-is for personal and educational use only. See [LICENSE](https://github.com/Harshal6927/muc?tab=Apache-2.0-1-ov-file) for details.
