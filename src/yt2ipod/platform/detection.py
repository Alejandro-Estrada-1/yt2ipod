"""Platform detection for yt2ipod.

Detects macOS, Linux, and Termux. Termux is NOT treated as generic Linux
when there are important differences (e.g., temp directories, storage paths).
"""

from __future__ import annotations

import os
import sys
import tempfile
from enum import Enum
from pathlib import Path


class PlatformType(Enum):
    """Detected platform type."""

    MACOS = "macos"
    LINUX = "linux"
    TERMUX = "termux"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Human-readable platform name."""
        names = {
            PlatformType.MACOS: "macOS",
            PlatformType.LINUX: "Linux",
            PlatformType.TERMUX: "Termux",
            PlatformType.UNKNOWN: "Unknown",
        }
        return names[self]


def detect_platform() -> PlatformType:
    """Detect the current platform.

    Detection order:
    1. Termux (checked first because it also reports as Linux)
    2. macOS
    3. Linux
    4. Unknown

    Termux is detected via the TERMUX_VERSION environment variable
    and the presence of /data/data/com.termux.
    """
    # Termux check first — it identifies as Linux but has critical differences
    if _is_termux():
        return PlatformType.TERMUX

    if sys.platform == "darwin":
        return PlatformType.MACOS

    if sys.platform.startswith("linux"):
        return PlatformType.LINUX

    return PlatformType.UNKNOWN


def _is_termux() -> bool:
    """Check if running inside Termux."""
    # Most reliable: TERMUX_VERSION environment variable
    if os.environ.get("TERMUX_VERSION"):
        return True

    # Fallback: check for Termux-specific path
    if os.path.isdir("/data/data/com.termux"):
        return True

    # Additional check: PREFIX environment variable
    prefix = os.environ.get("PREFIX", "")
    return bool(prefix.startswith("/data/data/com.termux"))


def get_temp_directory() -> Path:
    """Get a platform-appropriate temporary directory.

    Termux has known issues with the standard /tmp directory.
    This function returns a safe, writable temp directory for each platform.

    Returns:
        Path to a writable temporary directory.
    """
    platform = detect_platform()

    if platform == PlatformType.TERMUX:
        return _get_termux_temp()

    # macOS and Linux: use standard tempfile
    return Path(tempfile.gettempdir())


def _get_termux_temp() -> Path:
    """Get Termux-safe temporary directory.

    Tries, in order:
    1. $TMPDIR (if set and writable)
    2. $PREFIX/tmp (Termux standard)
    3. $HOME/.cache/yt2ipod/tmp
    """
    # 1. TMPDIR environment variable
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        path = Path(tmpdir)
        if path.is_dir() and os.access(str(path), os.W_OK):
            return path

    # 2. PREFIX/tmp (standard Termux temp)
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    termux_tmp = Path(prefix) / "tmp"
    if termux_tmp.is_dir() and os.access(str(termux_tmp), os.W_OK):
        return termux_tmp

    # 3. Fallback to home directory cache
    home = Path.home()
    cache_tmp = home / ".cache" / "yt2ipod" / "tmp"
    cache_tmp.mkdir(parents=True, exist_ok=True)
    return cache_tmp
