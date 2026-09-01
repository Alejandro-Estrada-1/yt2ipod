"""Filename sanitization utilities."""

from __future__ import annotations

import re

# Characters not allowed in Windows/FAT32/HFS+ file names
ILLEGAL_CHARS_REGEX = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Sanitize a string to be safe for use as a file name.

    Removes illegal characters, replaces them with `replacement`,
    and trims trailing/leading spaces.

    Args:
        name: The filename string to sanitize.
        replacement: Character to replace illegal characters with.

    Returns:
        The sanitized filename.
    """
    if not name:
        return "unnamed_track"

    # Replace illegal characters
    sanitized = ILLEGAL_CHARS_REGEX.sub(replacement, name)

    # Strip whitespace
    sanitized = sanitized.strip()

    # Avoid completely empty filenames
    if not sanitized:
        return "unnamed_track"

    return sanitized
