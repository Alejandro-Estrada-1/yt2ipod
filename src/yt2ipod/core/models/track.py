"""Track, TrackMetadata, and AudioInfo domain models.

These models represent the core data flowing through the pipeline:
- TrackMetadata: MusicBrainz-sourced metadata for a track
- AudioInfo: Technical audio properties from FFprobe
- Track: A complete work unit combining source, output, metadata, and artwork
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class TrackMetadata:
    """Metadata for a music track, primarily sourced from MusicBrainz.

    Important distinction:
        - `artist` is the track-level credit (e.g., "Little Jesus, Ximena Sariñana, Elsa y Elmar")
        - `album_artist` is the release-level artist (e.g., "Little Jesus")

    These MUST remain separate to avoid duplicate album issues in music players.
    """

    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    track_number: int | None = None
    track_total: int | None = None
    date: str = ""
    genre: str = ""

    # MusicBrainz identifiers — preserved as tags in the final MP3
    musicbrainz_recording_id: str = ""
    musicbrainz_release_id: str = ""
    musicbrainz_artist_id: str = ""

    @property
    def track_string(self) -> str:
        """Format track number as 'N/M' string (e.g., '2/10')."""
        if self.track_number is None:
            return ""
        if self.track_total is not None:
            return f"{self.track_number}/{self.track_total}"
        return str(self.track_number)

    @property
    def has_musicbrainz_ids(self) -> bool:
        """Check if MusicBrainz identifiers are present."""
        return bool(self.musicbrainz_recording_id)

    def display_summary(self) -> str:
        """Human-readable one-line summary."""
        parts = []
        if self.artist:
            parts.append(self.artist)
        if self.title:
            parts.append(self.title)
        return " — ".join(parts) if parts else "(unknown track)"


@dataclass
class AudioInfo:
    """Technical audio properties obtained from FFprobe.

    Used for validation after conversion and for duration comparison
    with MusicBrainz recordings.
    """

    codec: str = ""
    sample_rate: int = 0
    channels: int = 0
    bitrate: int = 0
    duration: float = 0.0  # seconds
    file_size: int = 0  # bytes

    # Artwork stream info (if embedded)
    has_artwork: bool = False
    artwork_width: int = 0
    artwork_height: int = 0

    def duration_difference_ms(self, musicbrainz_duration_ms: int) -> float:
        """Calculate absolute duration difference against a MusicBrainz duration.

        Args:
            musicbrainz_duration_ms: Duration from MusicBrainz in milliseconds.

        Returns:
            Absolute difference in seconds.
        """
        mb_seconds = musicbrainz_duration_ms / 1000.0
        return abs(self.duration - mb_seconds)

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return int(self.duration * 1000)

    @property
    def is_valid_mp3(self) -> bool:
        """Check if this represents a valid MP3 file."""
        return (
            self.codec in ("mp3", "mp3float")
            and self.sample_rate == 44100
            and self.channels == 2
            and self.duration > 0
        )

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes."""
        return self.file_size / (1024 * 1024)


@dataclass
class Track:
    """A complete work unit in the pipeline.

    Represents a track from source (YouTube URL or local file) through
    all pipeline stages to the final output file ready for transfer.
    """

    # Source
    source_url: str = ""
    source_path: Path | None = None

    # YouTube metadata (pre-MusicBrainz)
    youtube_title: str = ""
    youtube_artist: str = ""
    youtube_duration: float = 0.0  # seconds

    # Output
    output_path: Path | None = None

    # Resolved data (populated during pipeline)
    metadata: TrackMetadata = field(default_factory=TrackMetadata)
    audio_info: AudioInfo | None = None

    # Artwork reference (set during artwork stage)
    artwork_path: Path | None = None

    @property
    def display_name(self) -> str:
        """Best available display name for this track."""
        if self.metadata.title:
            return self.metadata.display_summary()
        if self.youtube_title:
            parts = []
            if self.youtube_artist:
                parts.append(self.youtube_artist)
            parts.append(self.youtube_title)
            return " — ".join(parts)
        if self.source_path:
            return self.source_path.stem
        return self.source_url or "(unknown)"

    @property
    def is_from_youtube(self) -> bool:
        """Check if this track originated from a YouTube URL."""
        return bool(self.source_url)

    @property
    def is_local_import(self) -> bool:
        """Check if this track is a local file import."""
        return bool(self.source_path) and not self.source_url
