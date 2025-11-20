# MU Soundboard 🎵🎮

Play audio files through your microphone in multiplayer games like CS, Battlefield, and COD using hotkeys. Built with Python and Rich for a beautiful CLI experience!

## ✨ Features

- 🎵 **Play audio through your mic** - Route sound to your virtual microphone
- ⌨️ **Hotkey support** - F1-F10 keys for instant sound playback
- 🎨 **Beautiful CLI** - Rich-click powered interface with colors and tables
- 🎛️ **Multiple formats** - Supports WAV, MP3, OGG, FLAC, M4A
- 🔊 **Auto-detection** - Finds VB-Cable and virtual audio devices automatically
- 📁 **Organized library** - Subdirectory support for sound organization
- ⚙️ **Persistent config** - Saves your settings to `~/.mu/config.json`
- 🎮 **Gaming ready** - Perfect for CS, Battlefield, COD, and more!

## 📋 Prerequisites

### 1. Python Environment
- **Python 3.13** or higher
- **uv** or **pip** for package management

### 2. Virtual Audio Cable
**CRITICAL**: You need a virtual audio device to route audio to your microphone.

**Recommended: VB-Cable (Free)**
1. Download from: https://vb-audio.com/Cable/
2. Install the driver
3. **Restart your computer** (required!)
4. This creates:
   - `CABLE Input` - Where your soundboard outputs audio
   - `CABLE Output` - What your game reads as a microphone

## 🚀 Installation

### Quick Start

1. **Install via uv or pip:**
   ```bash
   uv add mu
   # optional: with yt-dlp for downloading audio
   uv add mu[yt-dlp]
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
mu setup
```

The setup wizard will:
1. 📋 List all available audio devices in a beautiful table
2. 🔍 Auto-detect VB-Cable or similar virtual devices
3. ✓ Let you confirm or manually select the output device
4. 💾 Save your configuration to `~/.mu/config.json`

**IMPORTANT**: Select `CABLE Input` as the output device, not `CABLE Output`.

```
CABLE Input  ← Soundboard outputs HERE
     ↓
CABLE Output ← Game reads FROM here
```

## 🎮 Usage

### CLI Commands

MU provides a modern CLI with multiple commands:

```bash
# Setup and configuration
mu setup          # Run setup wizard
mu devices        # List all audio devices

# Sound management
mu sounds         # List available sounds in your library
mu play [name]    # Play a specific sound (prompts if no name)
mu stop           # Stop currently playing sound

# Hotkey control
mu hotkeys        # Show hotkey bindings (F1-F10)
mu listen         # Start hotkey listener (press ESC to stop)

# Interactive mode
mu interactive    # Launch full interactive menu

# Help
mu --help         # Show all commands
```

### Quick Workflow

1. **First time setup:**
   ```bash
   mu setup
   ```

2. **Check your sounds:**
   ```bash
   mu sounds
   ```

3. **Test a sound:**
   ```bash
   mu play rickroll
   ```

4. **Start gaming with hotkeys:**
   ```bash
   mu listen
   ```
   - Press F1-F10 to play sounds
   - Press ESC to stop

### Hotkey Bindings

The first 10 sounds (alphabetically) are automatically mapped to:
- **F1** → First sound
- **F2** → Second sound
- **F3** → Third sound
- ... through **F10**

View bindings:
```bash
mu hotkeys
```

### Interactive Menu Mode

For a full-featured text menu:
```bash
mu interactive
```

Menu options:
1. List all sounds
2. Play sound by name
3. View hotkey bindings
4. Start hotkey listener
5. Stop current sound
6. List audio devices
7. Change output device
0. Exit

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

```bash
# Download from YouTube (uses yt-dlp if installed)
yt-dlp -x --audio-format wav "https://youtube.com/watch?v=..."

# The file will be saved in your current directory
# Then move it to sounds/
```

## 🔧 Configuration

Configuration is automatically saved to `~/.mu/config.json`:

```json
{
  "output_device_id": 6,
  "sounds_dir": "C:/path/to/mu/sounds"
}
```

You can manually edit this file or reconfigure using:
```bash
mu setup
```

## 🎯 Gaming Tips

1. **Test First**: Always test sounds before joining a match
   ```bash
   mu play test-sound
   ```

2. **Volume Control**:
   - Adjust Windows master volume
   - Use audio editing software to normalize clips
   - Set in-game voice volume appropriately

3. **Quick Access**:
   - Keep a terminal with `mu listen` running
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
mu setup  # Run again after restart
```

### "Teammates can't hear the audio"
**Check**:
1. Game microphone set to `CABLE Output` ✓
2. Soundboard output set to `CABLE Input` ✓
3. Test with: `mu play test-sound`

**Fix**:
```bash
mu devices  # Verify device IDs
mu setup    # Reconfigure if needed
```

### "Audio plays on my speakers, not through mic"
**Problem**: Wrong output device selected

**Solution**:
```bash
mu devices  # Find CABLE Input ID
mu setup    # Select correct device
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
mu interactive  # Then select option 4
```

### "Audio quality is poor"
**Improve quality**:
1. Use WAV or high-bitrate MP3 files
2. Match sample rate to your device (usually 48000 Hz)
3. Normalize audio levels
4. Check VB-Cable settings in Windows Sound Control Panel

### "Configuration not saving"
**Check**: Permissions for `~/.mu/` directory

```powershell
# Windows - check directory
ls ~\.mu

# If missing, create manually
mkdir ~\.mu
```

## 🏗️ Architecture

This project implements a clean software architecture:

```
┌─────────────┐
│  CLI Layer  │  ← Rich-click commands (cli.py)
└──────┬──────┘
       │
┌──────▼──────┐
│   Config    │  ← Settings management (config.py)
└──────┬──────┘
       │
┌──────▼──────────────┬──────────────┐
│   Soundboard        │ Audio Manager│
│  (hotkeys, sounds)  │ (devices, io)│
└─────────────────────┴──────────────┘
          │                    │
          └──────┬─────────────┘
                 ▼
        ┌────────────────┐
        │  Audio Drivers │
        │ (sounddevice)  │
        └───────┬────────┘
                ▼
        Virtual Audio Device
        (VB-Cable, etc.)
```

**Flow**:
1. User runs command → CLI parses → Config loads settings
2. Soundboard scans sounds → Sets up hotkeys
3. User presses F1 → Hotkey handler triggered
4. Audio Manager loads file → Outputs to virtual device
5. Game reads from virtual device → Teammates hear sound

## 📁 Project Structure

```
mu/
├── src/
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # Rich-click CLI commands
│   ├── config.py            # Configuration management
│   ├── audio_manager.py     # Audio device & playback
│   ├── soundboard.py        # Sound library & hotkeys
│   └── main.py              # Entry point
├── sounds/                  # Audio files directory
│   └── README.md            # Sound library guide
├── pyproject.toml           # Project metadata & dependencies
├── README.md                # This file
└── idea.md                  # Original design document
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

This project is provided as-is for personal and educational use only. See [LICENSE](https://github.com/Harshal6927/mu?tab=Apache-2.0-1-ov-file) for details.
