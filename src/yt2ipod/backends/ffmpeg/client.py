"""FFmpeg backend for audio conversion and metadata embedding.

Acts as an adapter over the ffmpeg and ffprobe system binaries via ProcessRunner.
Converts audio to MP3 320kbps and injects ID3v2 metadata with cover artwork.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from yt2ipod.core.models.errors import ConversionError, DependencyError, ProcessExecutionError
from yt2ipod.core.models.events import ConversionProgress
from yt2ipod.core.models.track import TrackMetadata
from yt2ipod.utils.logging import get_logger
from yt2ipod.utils.runner import ProcessRunner

logger = get_logger(__name__)


# Progress parsing regex for ffmpeg stderr
# Example: "size=    1024kB time=00:01:23.45 bitrate= 320.0kbits/s speed=4.5x"
TIME_REGEX = re.compile(r"time=(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}\.\d{2})")


class FFmpegClient:
    """Client for executing ffmpeg and ffprobe operations."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> None:
        """Initialize the client.

        Args:
            ffmpeg_path: Command or path to ffmpeg binary.
            ffprobe_path: Command or path to ffprobe binary.
        """
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path

    async def check_dependency(self) -> None:
        """Verify ffmpeg and ffprobe are installed and available.

        Raises:
            DependencyError: If binaries are not found or fail to execute.
        """
        for bin_name in (self.ffmpeg, self.ffprobe):
            if not shutil.which(bin_name):
                raise DependencyError(
                    f"{bin_name} is not installed or not in PATH.",
                    dependency=bin_name,
                    install_hint="macOS: brew install ffmpeg | Linux: apt/pacman/dnf install ffmpeg",
                )
            try:
                await ProcessRunner.run([bin_name, "-version"], check=True)
            except ProcessExecutionError as e:
                raise DependencyError(f"{bin_name} exists but failed to execute: {e}") from e

    async def get_duration(self, input_path: Path) -> float:
        """Get the exact duration of a media file using ffprobe.

        Args:
            input_path: Path to the media file.

        Returns:
            Duration in seconds.

        Raises:
            ConversionError: If duration cannot be extracted.
        """
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]

        try:
            result = await ProcessRunner.run(cmd, check=True)
            return float(result.stdout.strip())
        except (ProcessExecutionError, ValueError) as e:
            raise ConversionError(f"Failed to get duration for {input_path.name}") from e

    async def convert_to_mp3(
        self,
        input_path: Path,
        output_path: Path,
        bitrate: str = "320k",
        total_duration: float | None = None,
    ) -> AsyncIterator[ConversionProgress]:
        """Convert audio to MP3 and yield progress.

        Args:
            input_path: Input file path.
            output_path: Output file path (.mp3).
            bitrate: Audio bitrate (default 320k).
            total_duration: Total duration of the track for progress calculation.
                            If None, get_duration will be called automatically.

        Yields:
            ConversionProgress events.

        Raises:
            ConversionError: If the conversion fails.
        """
        if total_duration is None:
            total_duration = await self.get_duration(input_path)

        # ffmpeg -y -i input -c:a libmp3lame -b:a 320k output
        cmd = [
            self.ffmpeg,
            "-y",  # overwrite
            "-i", str(input_path),
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            str(output_path),
        ]

        logger.info(f"Converting {input_path.name} to MP3...")

        try:
            # ffmpeg logs progress to stderr
            async for stream_name, line in ProcessRunner.run_stream(cmd, check=True):
                if stream_name == "stderr":
                    match = TIME_REGEX.search(line)
                    if match and total_duration > 0:
                        h = float(match.group("hour"))
                        m = float(match.group("minute"))
                        s = float(match.group("second"))
                        current_time = h * 3600 + m * 60 + s

                        percent = (current_time / total_duration) * 100.0
                        percent = min(100.0, max(0.0, percent))
                        yield ConversionProgress(percent=percent)
        except ProcessExecutionError as e:
            raise ConversionError(f"FFmpeg conversion failed: {e.stderr.splitlines()[-1] if e.stderr else str(e)}") from e

        # Final 100% event
        yield ConversionProgress(percent=100.0)

    async def embed_metadata(
        self,
        input_path: Path,
        output_path: Path,
        metadata: TrackMetadata,
        artwork_path: Path | None = None,
    ) -> None:
        """Embed ID3v2 metadata and artwork into an MP3 file.

        Creates a new file at output_path. Does not re-encode audio.

        Args:
            input_path: Path to the source MP3 file.
            output_path: Path to write the tagged MP3 file.
            metadata: TrackMetadata object.
            artwork_path: Optional path to the cover image.

        Raises:
            ConversionError: If tagging fails.
        """
        cmd = [
            self.ffmpeg,
            "-y",
            "-i", str(input_path),
        ]

        # Map metadata fields to FFmpeg metadata keys
        meta_args = [
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]

        if metadata.title:
            meta_args.extend(["-metadata", f"title={metadata.title}"])
        if metadata.artist:
            meta_args.extend(["-metadata", f"artist={metadata.artist}"])
        if metadata.album:
            meta_args.extend(["-metadata", f"album={metadata.album}"])
        if metadata.album_artist:
            meta_args.extend(["-metadata", f"album_artist={metadata.album_artist}"])
        if metadata.date:
            meta_args.extend(["-metadata", f"date={metadata.date}"])
        if metadata.genre:
            meta_args.extend(["-metadata", f"genre={metadata.genre}"])

        # Track number handling: 1 or 1/12
        if metadata.track_number is not None:
            track_str = str(metadata.track_number)
            if metadata.track_total is not None:
                track_str += f"/{metadata.track_total}"
            meta_args.extend(["-metadata", f"track={track_str}"])

        if artwork_path and artwork_path.exists():
            # Add artwork as a second input stream
            cmd.extend(["-i", str(artwork_path)])

            # Map stream 0 (audio) and stream 1 (video/image)
            meta_args.extend([
                "-map", "0:0",
                "-map", "1:0",
                "-c", "copy",          # Copy audio
                "-c:v", "mjpeg",       # Ensure image is jpeg
                "-disposition:v", "attached_pic"
            ])
        else:
            meta_args.extend(["-c", "copy"])  # Just copy audio

        cmd.extend(meta_args)
        cmd.append(str(output_path))

        try:
            await ProcessRunner.run(cmd, check=True)
        except ProcessExecutionError as e:
            raise ConversionError(f"Failed to embed metadata: {e.stderr.splitlines()[-1] if e.stderr else str(e)}") from e
