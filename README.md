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

- **Automatic pipeline**: `./yt2ipod "URL"` does everything
- **Interactive mode**: Textual TUI with menu navigation
- **Plain mode**: `--plain` and `--json` for automation
- **Multiple transfer methods**: AFC, AFC2, USB-SSH, Wi-Fi SSH
- **Correct metadata**: MusicBrainz identification with scoring
- **Correct artwork**: Cover Art Archive with release-linked validation
- **Local file import**: Process existing MP3 files
- **Cross-platform**: macOS, Linux, Termux
- **Extensible**: Modular architecture with pluggable backends

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

The architecture supports any legacy Apple device. The first test device is:

- iPod touch 5G (iOS 9.3.5, 32-bit)

Planned support includes iPod touch 1G–7G and legacy iPhones.

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

#### macOS (Homebrew)

```bash
brew install yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse
```

#### Termux

```bash
pkg install python yt-dlp ffmpeg openssh
```

#### Debian/Ubuntu

```bash
sudo apt install yt-dlp ffmpeg openssh-client usbmuxd libimobiledevice-utils ifuse
```

#### Arch Linux

```bash
sudo pacman -S yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse
```

#### Fedora

```bash
sudo dnf install yt-dlp ffmpeg openssh usbmuxd libimobiledevice ifuse
```

## Installation

```bash
# Clone the repository
git clone https://github.com/yt2ipod/yt2ipod.git
cd yt2ipod

# Install in development mode
pip install -e ".[dev]"

# Or with all optional dependencies
pip install -e ".[all,dev]"
```

## Usage

### Automatic mode

```bash
./yt2ipod "https://youtu.be/VIDEO_ID"
```

### Interactive mode

```bash
./yt2ipod
```

### Plain mode (no TUI)

```bash
./yt2ipod "URL" --plain
```

### JSON output (for automation)

```bash
./yt2ipod "URL" --json
```

### Transfer existing files

```bash
./yt2ipod --transfer file1.mp3 file2.mp3
```

### Import local music

```bash
./yt2ipod --import-local song.mp3
```

### Options

| Flag | Description |
|------|-------------|
| `--plain` | Plain terminal output (no TUI) |
| `--json` | JSON output for automation |
| `--output-dir DIR` | Output directory |
| `--keep-temp` | Keep temporary files (debugging) |
| `--no-transfer` | Prepare files, skip transfer |
| `--transfer FILE...` | Transfer existing files to device |
| `--import-local FILE...` | Import and process local audio |
| `--version` | Show version |

## Transfer Methods

| Method | Connection | Requirements |
|--------|-----------|--------------|
| AFC | USB | libimobiledevice, ifuse |
| AFC2 | USB | AFC2 tweak (jailbreak) |
| USB-SSH | USB | usbmuxd, OpenSSH, jailbreak |
| Wi-Fi SSH | Wi-Fi | OpenSSH, jailbreak |

The transfer manager automatically selects the best available method.

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

