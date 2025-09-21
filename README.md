# AudioWindowCMD

A simple cross-platform Python application that provides an interactive command-line shell to display images and control audio playback.

Useful for running TTRPG sessions. Rapidly change the image you want to show your players and set the mood with music/sounds effects, all via command line.

## Features

- Display images in a resizable Tkinter window
- Play audio files (MP3, WAV, OGG) via shell commands
- Volume control and playback management
- Window controls (fullscreen, restore, minimize)
- Command history (during session) and tab completion
- Cross-platform support (Windows and Linux)

## Requirements

- **Python 3.10+**
- **pip** package manager

### Dependencies

- `pillow>=11.3.0` - Image processing and display
- `pygame>=2.6.1` - Audio playback functionality
- `screeninfo>=0.8.1` - Multiple monitor screen resolution detection

## Installation

1. Clone or download the project
2. Navigate to the project directory
3. Install dependencies:

```bash
pip install -r requirements.txt
```
## Usage

From the project root directory, run:

```bash
python -m shell_app.main
```
> **Note:** On Windows, use `python` instead of `python3` if needed.

## Shell Commands

| Command | Description | Example |
|---------|-------------|---------|
| `show <image_path>` | Display an image in the window | `show assets/images/sample_image.jpg` |
| `play <audio_path>` | Play an audio file | `play assets/audio/sample_sound.mp3` |
| `volume <0-100>` | Set playback volume (0-100) OR simply request volume when no arg is given | `volume`, `volume 50` |
| `fullscreen` | Switch to fullscreen mode | `fullscreen` |
| `minimize` | Minimize the window | `minimize` |
| `restore` | Restore window from fullscreen or minimization | `restore` |
| `stop` | Stop audio playback | `stop` |
| `exit` | Close the application | `exit` |

## Supported Formats

- **Images:** All formats supported by PIL/Pillow (JPEG, PNG, GIF, etc.)
- **Audio:** MP3, WAV, OGG