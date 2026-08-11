"""Pipeline event model.

Structured events emitted by the pipeline for consumption by any interface
(Textual TUI, plain CLI, JSON output). The pipeline never prints directly —
it emits events, and the interface decides how to present them.

All events are frozen dataclasses (immutable after creation).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Base ---

@dataclass(frozen=True)
class PipelineEvent:
    """Base class for all pipeline events."""
    pass


# --- Download ---

@dataclass(frozen=True)
class DownloadStarted(PipelineEvent):
    """Emitted when a download begins."""

    url: str = ""
    title: str = ""


@dataclass(frozen=True)
class DownloadProgress(PipelineEvent):
    """Emitted periodically during download."""

    percent: float = 0.0  # 0.0 to 100.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: str = ""  # human-readable, e.g. "1.2 MiB/s"


@dataclass(frozen=True)
class DownloadCompleted(PipelineEvent):
    """Emitted when download finishes successfully."""

    title: str = ""
    duration: float = 0.0  # seconds (download time)
    file_size: int = 0


# --- Conversion ---

@dataclass(frozen=True)
class ConversionStarted(PipelineEvent):
    """Emitted when audio conversion begins."""

    source_format: str = ""
    target_format: str = "mp3"


@dataclass(frozen=True)
class ConversionProgress(PipelineEvent):
    """Emitted periodically during conversion."""

    percent: float = 0.0


@dataclass(frozen=True)
class ConversionCompleted(PipelineEvent):
    """Emitted when conversion finishes successfully."""

    duration: float = 0.0
    output_size: int = 0


# --- Metadata ---

@dataclass(frozen=True)
class MetadataSearchStarted(PipelineEvent):
    """Emitted when MusicBrainz search begins."""

    artist: str = ""
    title: str = ""


@dataclass(frozen=True)
class MetadataMatched(PipelineEvent):
    """Emitted when a MusicBrainz match is found."""

    artist: str = ""
    title: str = ""
    album: str = ""
    recording_id: str = ""
    confidence: float = 0.0  # 0.0 to 1.0


@dataclass(frozen=True)
class MetadataNotFound(PipelineEvent):
    """Emitted when no suitable MusicBrainz match is found."""

    artist: str = ""
    title: str = ""
    reason: str = ""


# --- Artwork ---

@dataclass(frozen=True)
class ArtworkSearchStarted(PipelineEvent):
    """Emitted when Cover Art Archive search begins."""

    release_id: str = ""


@dataclass(frozen=True)
class ArtworkFound(PipelineEvent):
    """Emitted when artwork is found and validated."""

    width: int = 0
    height: int = 0
    release_id: str = ""


@dataclass(frozen=True)
class ArtworkNotFound(PipelineEvent):
    """Emitted when no artwork could be found for any release."""

    release_id: str = ""
    reason: str = ""


# --- Device ---

@dataclass(frozen=True)
class DeviceDetected(PipelineEvent):
    """Emitted when a device is detected."""

    model: str = ""
    ios_version: str = ""
    connection: str = ""
    capabilities: str = ""  # summary string


@dataclass(frozen=True)
class DeviceNotFound(PipelineEvent):
    """Emitted when no compatible device is detected."""
    pass


# --- Transfer ---

@dataclass(frozen=True)
class TransferStarted(PipelineEvent):
    """Emitted when file transfer begins."""

    method: str = ""
    file_count: int = 0
    total_bytes: int = 0


@dataclass(frozen=True)
class TransferProgress(PipelineEvent):
    """Emitted periodically during transfer."""

    percent: float = 0.0
    current_file: str = ""
    files_completed: int = 0
    files_total: int = 0


@dataclass(frozen=True)
class TransferCompleted(PipelineEvent):
    """Emitted when transfer finishes successfully."""

    method: str = ""
    files_transferred: int = 0
    duration: float = 0.0


@dataclass(frozen=True)
class TransferFailed(PipelineEvent):
    """Emitted when transfer fails."""

    method: str = ""
    error: str = ""


# --- Cleanup ---

@dataclass(frozen=True)
class CleanupStarted(PipelineEvent):
    """Emitted when cleanup begins."""

    file_count: int = 0


@dataclass(frozen=True)
class CleanupCompleted(PipelineEvent):
    """Emitted when cleanup finishes."""

    files_removed: int = 0
    bytes_freed: int = 0


# --- Tagging ---

@dataclass(frozen=True)
class TaggingStarted(PipelineEvent):
    """Emitted when metadata/artwork embedding begins."""
    pass


@dataclass(frozen=True)
class TaggingCompleted(PipelineEvent):
    """Emitted when metadata/artwork embedding finishes."""

    has_artwork: bool = False
    has_metadata: bool = False
