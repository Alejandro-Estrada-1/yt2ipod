"""Application configuration models.

Separates Python-side config from system-level settings.
No passwords are stored. SSH identity is via key file path only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class InterfaceMode(Enum):
    """User interface mode."""

    INTERACTIVE = "interactive"
    PLAIN = "plain"
    JSON = "json"


class DuplicatePolicy(Enum):
    """How to handle duplicate output files."""

    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


class DownloadQuality(Enum):
    """Audio download/conversion quality."""

    BEST = "best"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def ffmpeg_quality(self) -> int:
        """FFmpeg VBR quality parameter (0 = best, 9 = worst)."""
        quality_map = {
            DownloadQuality.BEST: 0,
            DownloadQuality.HIGH: 2,
            DownloadQuality.MEDIUM: 4,
            DownloadQuality.LOW: 6,
        }
        return quality_map[self]


@dataclass
class SSHSettings:
    """SSH connection settings.

    No password storage by design — uses key-based auth or
    prompts the user interactively.
    """

    host: str = ""
    port: int = 22
    username: str = ""
    identity_file: Path | None = None

    @property
    def is_configured(self) -> bool:
        """Check if SSH settings have been provided."""
        return bool(self.host) and bool(self.username)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    # Output
    output_dir: Path | None = None
    keep_temp: bool = False

    # Audio
    download_quality: DownloadQuality = DownloadQuality.BEST

    # Transfer
    preferred_transfer_order: list[str] = field(
        default_factory=lambda: ["afc", "afc2", "usb_ssh", "wifi_ssh"]
    )
    ssh_settings: SSHSettings = field(default_factory=SSHSettings)

    # Files
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME

    # Interface
    interface_mode: InterfaceMode = InterfaceMode.INTERACTIVE

    # Metadata
    genre_fallback: str = ""

    @property
    def effective_output_dir(self) -> Path:
        """Resolved output directory (defaults to current directory)."""
        if self.output_dir is not None:
            return self.output_dir
        return Path.cwd()
