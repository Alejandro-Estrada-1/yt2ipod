"""System file and directory selection dialogs.

Provides helper functions to trigger native GUI file choosers (e.g. Zenity)
when running in graphical desktop environments, with graceful fallbacks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def is_gui_dialog_available() -> bool:
    """Check if a graphical file picker (zenity) is available in the current environment."""
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    has_zenity = shutil.which("zenity") is not None
    return has_display and has_zenity


def pick_files_dialog(
    title: str = "Select Audio Files",
    multiple: bool = True,
    file_filter: str = "Audio Files | *.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac *.wma *.alac",
) -> list[Path]:
    """Open a native file selection dialog to choose one or more files.

    Args:
        title: Title of the file chooser window.
        multiple: Whether to allow selecting multiple files.
        file_filter: Filter pattern for file extensions.

    Returns:
        List of Path objects for selected files, or empty list if cancelled.
    """
    if not is_gui_dialog_available():
        return []

    cmd = ["zenity", "--file-selection", f"--title={title}"]
    if multiple:
        cmd.extend(["--multiple", "--separator=|"])
    if file_filter:
        cmd.append(f"--file-filter={file_filter}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return []

        paths_str = res.stdout.strip()
        if multiple:
            paths = [Path(p.strip()) for p in paths_str.split("|") if p.strip()]
        else:
            paths = [Path(paths_str)]

        return [p for p in paths if p.exists()]
    except Exception:
        return []


def pick_directory_dialog(title: str = "Select Music Directory") -> Path | None:
    """Open a native directory selection dialog.

    Args:
        title: Title of the directory chooser window.

    Returns:
        Selected Path if chosen, or None if cancelled.
    """
    if not is_gui_dialog_available():
        return None

    cmd = ["zenity", "--file-selection", "--directory", f"--title={title}"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return None

        path = Path(res.stdout.strip())
        return path if path.is_dir() else None
    except Exception:
        return None
