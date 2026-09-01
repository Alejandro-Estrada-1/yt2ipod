"""Artwork domain model.

Represents a cover art image discovered from Cover Art Archive,
validated and ready for embedding into the final MP3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Preferred artwork dimensions
ARTWORK_TARGET_WIDTH = 500
ARTWORK_TARGET_HEIGHT = 500
ARTWORK_VALID_FORMATS = frozenset({"jpeg", "jpg", "png"})


@dataclass
class Artwork:
    """Cover art image for a track/release.

    Linked to a specific MusicBrainz release to avoid mismatches
    (e.g., getting artwork from a different artist's identically-named release).
    """

    path: Path | None = None
    url: str = ""
    width: int = 0
    height: int = 0
    format: str = ""  # "jpeg", "png", etc.

    # MusicBrainz release this artwork belongs to
    release_id: str = ""
    release_title: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if this artwork meets quality requirements.

        Valid artwork must:
        - Have correct dimensions (500x500)
        - Be a supported image format (JPEG or PNG)
        - Have an associated file path
        """
        return (
            self.path is not None
            and self.width == ARTWORK_TARGET_WIDTH
            and self.height == ARTWORK_TARGET_HEIGHT
            and self.format.lower() in ARTWORK_VALID_FORMATS
        )

    @property
    def is_downloaded(self) -> bool:
        """Check if the artwork file has been downloaded."""
        return self.path is not None and self.path.exists()

    @property
    def dimensions_string(self) -> str:
        """Human-readable dimensions (e.g., '500x500')."""
        return f"{self.width}x{self.height}"

    @property
    def has_release_link(self) -> bool:
        """Check if this artwork is linked to a specific release."""
        return bool(self.release_id)
