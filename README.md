# yt2ipod

Download music from YouTube, identify metadata via MusicBrainz, and transfer to legacy iPod/iPhone devices.

## What is yt2ipod?

yt2ipod is a specialized tool that automates the complete workflow of:

1. Downloading audio from YouTube (via yt-dlp)
2. Converting to MP3 (via FFmpeg)
3. Identifying correct metadata (via MusicBrainz)
4. Obtaining cover artwork (via Cover Art Archive)
5. Embedding metadata and artwork into the MP3
6. Transferring to legacy Apple devices (iPod touch, older iPhones)

It is **not** an iTunes replacement or an iMazing clone. It is a focused tool built around open tooling, Linux, Termux, macOS, and multiple transfer backends.

## Features

- **Automatic pipeline**: `./yt2ipod "URL"` downloads, converts, tags, and syncs
- **Interactive mode**: Rich Textual TUI with full keyboard and mouse navigation
- **Batch folder import**: Import and tag entire folders of audio files (`.mp3`, `.wav`, `.m4a`, `.flac`, etc.) in one command
- **Native GUI file pickers**: Visual file and directory dialogs (via `zenity`) in desktop environments
- **Plain mode**: `--plain` and `--json` for CLI scripts and headless automation
- **Multiple transfer backends**: AFC (Standard USB), AFC2 (Jailbroken USB Root), USB-SSH, Wi-Fi SSH
- **Forced transfer selection**: Choose automatic detection or force a specific transfer protocol
- **Accurate metadata**: MusicBrainz integration with smart scoring, noise cleaning, and demo/live version penalties
- **Official artwork**: High-resolution album covers from Cover Art Archive
- **Cross-platform**: macOS, Linux, Termux (Android)
- **Extensible**: Modular architecture with pluggable adapters

## Architecture

```
CORE          — Domain models, pipeline logic, no platform knowledge
INTERFACES    — Textual TUI, plain CLI, JSON output
BACKENDS      — yt-dlp, FFmpeg, MusicBrainz, Cover Art Archive, SSH, AFC
PLATFORM      — macOS, Linux, Termux adapters
```

The core never knows which platform or interface is running. Interfaces receive structured events from the pipeline. Backends are adapters for external tools.

## Supported Platforms

| Platform | Status |
|----------|--------|
| macOS    | Supported |
| Linux    | Supported |
| Termux   | Supported (Android) |

## Supported Devices

The architecture supports any legacy Apple device. The primary test devices include:

- iPod touch 5G (iOS 9.3.5, 32-bit)
- iPod touch 1G–7G
- Legacy iPhones (iPhone 2G, 3G, 3GS, 4, 4S, 5, etc.)

## Requirements

### Python

- Python 3.9+

### System Dependencies

These are **not** Python packages — install them via your system package manager:

| Dependency | Purpose | Required |
|------------|---------|----------|
| yt-dlp | YouTube download | For YouTube downloads |
| ffmpeg | Audio conversion | For audio processing |
| ffprobe | Audio validation | For audio processing |
| OpenSSH | SSH transfer | For SSH transport |
| usbmuxd | USB communication | For USB device detection |
| libimobiledevice | iOS device info | For device detection |
| ifuse | AFC mounting | For AFC transport |
| zenity | Native GUI file/folder chooser | Optional (Linux Desktop) |

#### macOS (Homebrew)

```bash
brew install yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse
```

#### Termux

```bash
pkg install python yt-dlp ffmpeg openssh libjpeg-turbo libtiff freetype libimobiledevice usbmuxd ifuse
```

#### Debian/Ubuntu

```bash
sudo apt install yt-dlp ffmpeg openssh-client usbmuxd libimobiledevice-utils ifuse zenity
```

#### Arch Linux

```bash
sudo pacman -S yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse zenity
```

#### Fedora

```bash
sudo dnf install yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse zenity
```

## Installation

The easiest way to install `yt2ipod` and verify its system dependencies is using the provided automated script:

```bash
# Clone the repository
git clone https://github.com/yt2ipod/yt2ipod.git
cd yt2ipod

# Run the automated installer
./scripts/install.sh
```

The installer will verify if you have the required system dependencies (`ffmpeg`, `yt-dlp`, `iproxy`, `ifuse`) and install the python package inside your active virtual environment or user site.

To uninstall, simply run:
```bash
./scripts/uninstall.sh
```

## Usage

### Automatic mode (YouTube)

```bash
./yt2ipod "https://youtu.be/VIDEO_ID"
```

### Interactive mode (TUI)

```bash
./yt2ipod
```

Inside the TUI:
- **Download from YouTube**: Download, tag, and transfer in one step with dynamic transfer method selector.
- **Import Local Music**: Choose a single file or an entire folder of songs (`.wav`, `.m4a`, `.mp3`, `.flac`), identify metadata on MusicBrainz, fetch album covers, tag, and transfer in batch.
- **Select Files to Transfer**: Visually pick existing `.mp3` files from any directory or folder and sync them directly to your device.
- **Device Info**: View connected iPod/iPhone status, serial number, iOS version, and available transfer interfaces.

### Plain mode (no TUI)

```bash
./yt2ipod "URL" --plain
```

### JSON output (for automation)

```bash
./yt2ipod "URL" --json
```

### Transfer existing MP3 files directly

```bash
./yt2ipod --transfer song1.mp3 song2.mp3
```

### Import and tag local music (file or directory batch)

```bash
# Single file
./yt2ipod --import-local song.wav

# Entire folder (batch import)
./yt2ipod --import-local ~/Music/MyAlbum/
```

### Options

| Flag | Description |
|------|-------------|
| `--plain` | Plain terminal output (no TUI) |
| `--json` | JSON output for automation |
| `--output-dir DIR` | Output directory for downloaded/processed MP3s |
| `--keep-temp` | Keep temporary intermediate files (for debugging) |
| `--no-transfer` | Process audio and tag locally, skip device transfer |
| `--transfer FILE...` | Transfer existing MP3 files directly to device |
| `--import-local PATH...`| Import and process local audio file or folder |
| `--cookies FILE` | Optional path to `cookies.txt` for YouTube |
| `--version` | Show version |

## Transfer Methods

| Method | Connection | Requirements |
|--------|-----------|--------------|
| AFC | USB | libimobiledevice, ifuse |
| AFC2 | USB | AFC2 tweak (jailbreak) |
| USB-SSH | USB | usbmuxd, OpenSSH, jailbreak |
| Wi-Fi SSH | Wi-Fi | OpenSSH, jailbreak |

The transfer manager automatically selects the best available method, or you can force a specific method directly in the TUI dropdown.

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
# Unit tests only (no network)
python -m pytest tests/unit/ -v

# All tests
python -m pytest -v

# With coverage
python -m pytest --cov=yt2ipod tests/
```

### Lint

```bash
python -m ruff check src/ tests/
python -m ruff format src/ tests/
```

### Project structure

```
src/yt2ipod/
├── core/           # Domain models, pipeline, no platform deps
│   ├── models/     # Track, Device, Artwork, Config, Events, Errors
│   ├── pipeline/   # Pipeline orchestration
│   ├── metadata/   # Metadata resolution
│   ├── artwork/    # Artwork discovery
│   ├── device/     # Device detection
│   ├── transfer/   # Transfer management
│   ├── filesystem/ # Filesystem abstraction
│   └── cleanup/    # Temp file management
├── interfaces/     # UI implementations
│   ├── textual/    # Textual TUI
│   ├── plain/      # Plain terminal
│   └── common/     # Shared components
├── backends/       # External tool adapters
│   ├── youtube/    # yt-dlp
│   ├── ffmpeg/     # FFmpeg/FFprobe
│   ├── musicbrainz/# MusicBrainz API
│   ├── coverartarchive/ # Cover Art Archive
│   ├── libimobiledevice/
│   ├── ifuse/
│   └── openssh/
├── platform/       # Platform-specific adapters
│   ├── macos/
│   ├── linux/
│   └── termux/
├── config/         # Configuration
└── utils/          # Logging, utilities
```

## Troubleshooting

### Missing dependencies

yt2ipod checks for required tools before running operations:

```
Missing dependency: ffmpeg

Install it using:
  brew install ffmpeg
```

### Termux

Termux requires special handling for temporary directories. yt2ipod automatically detects Termux and uses appropriate paths.

### Device not detected

Ensure usbmuxd is running and the device is connected via USB. On Linux:

```bash
sudo systemctl start usbmuxd
```

### YouTube rate limits / Age-restricted videos (Cookies)

If you get blockages (e.g. `HTTP Error 429: Too Many Requests`) or try to download age-restricted music, you can optionally provide your browser's YouTube session cookies. 

**This is entirely optional** and not needed under normal circumstances.

1. Install a browser extension like *Get cookies.txt LOCALLY* to export your cookies in Netscape format.
2. Save the exported file as `cookies.txt`.
3. Pass the cookies to the application:
   - **CLI**: Use the `--cookies cookies.txt` option.
   - **TUI**: The application will automatically detect a `cookies.txt` file if it is located in the root directory.

