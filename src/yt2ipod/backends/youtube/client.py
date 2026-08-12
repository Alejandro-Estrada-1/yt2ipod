"""YouTube download backend using yt-dlp.

Acts as an adapter over the yt-dlp system binary via ProcessRunner.
Does not import yt_dlp directly to avoid Python environment conflicts,
especially on constrained environments like Termux where system packages
are updated independently.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from yt2ipod.core.models.config import DownloadQuality
from yt2ipod.core.models.errors import DependencyError, DownloadError, ProcessExecutionError
from yt2ipod.core.models.events import DownloadProgress
from yt2ipod.core.models.track import Track
from yt2ipod.utils.logging import get_logger
from yt2ipod.utils.runner import ProcessRunner

logger = get_logger(__name__)


# Progress parsing regex for yt-dlp stdout
# Example: "[download]  45.0% of   3.45MiB at    1.20MiB/s ETA 00:01"
PROGRESS_REGEX = re.compile(r"\[download\]\s+(?P<percent>[\d\.]+)%\s+of\s+(?P<size>[~]?[\d\.]+[a-zA-Z]+)(?:\s+at\s+(?P<speed>[\d\.]+[a-zA-Z]+/s))?")


class YtDlpClient:
    """Client for executing yt-dlp operations."""

    def __init__(self, binary_path: str = "yt-dlp", cookies_file: Path | None = None) -> None:
        """Initialize the client.

        Args:
            binary_path: Command or path to yt-dlp binary.
            cookies_file: Path to a cookies file for authentication.
        """
        self.binary_path = binary_path
        self.cookies_file = cookies_file

    def _get_cookies_args(self) -> list[str]:
        """Get the yt-dlp arguments for passing cookies if available."""
        # 1. Use configured cookies file if specified and exists
        if self.cookies_file is not None and self.cookies_file.exists():
            return ["--cookies", str(self.cookies_file)]
        
        # 2. Automatically look for a cookies.txt file in the workspace directory
        default_cookies = Path("cookies.txt")
        if default_cookies.exists():
            return ["--cookies", str(default_cookies)]
            
        return []

    async def check_dependency(self) -> None:
        """Verify yt-dlp is installed and available.

        Raises:
            DependencyError: If yt-dlp is not found.
        """
        if not shutil.which(self.binary_path):
            raise DependencyError(
                "yt-dlp is not installed or not in PATH.",
                dependency="yt-dlp",
                install_hint="macOS: brew install yt-dlp | Termux: pkg install yt-dlp | Linux: apt/pacman/dnf install yt-dlp",
            )
        try:
            await ProcessRunner.run([self.binary_path, "--version"], check=True)
        except ProcessExecutionError as e:
            raise DependencyError(f"yt-dlp exists but failed to execute: {e}") from e

    def _map_error(self, e: ProcessExecutionError) -> DownloadError:
        """Map raw process errors to human-readable DownloadErrors."""
        stderr = e.stderr.lower()
        if "sign in to confirm you're not a bot" in stderr:
            msg = "YouTube bot detection triggered. Authentication or cookies required."
        elif "http error 429" in stderr or "too many requests" in stderr:
            msg = "YouTube rate limit exceeded (HTTP 429)."
        elif "unsupported url" in stderr:
            msg = "Invalid or unsupported URL."
        elif "video is unavailable" in stderr:
            msg = "Video is unavailable or private."
        elif "requested format is not available" in stderr:
            msg = "Requested audio format is not available for this video."
        else:
            msg = f"yt-dlp failed: {e.stderr.splitlines()[-1] if e.stderr else 'Unknown error'}"

        return DownloadError(msg, cause=e)

    async def get_metadata(self, url: str) -> Track:
        """Quickly fetch basic video metadata without downloading.

        Args:
            url: YouTube URL.

        Returns:
            Track object populated with source_url and youtube_* fields.

        Raises:
            DownloadError: If metadata extraction fails.
        """
        cmd = [
            self.binary_path,
            "--dump-json",
            "--no-playlist",
            "--quiet",
        ] + self._get_cookies_args() + [url]

        try:
            result = await ProcessRunner.run(cmd, check=True)
        except ProcessExecutionError as e:
            raise self._map_error(e) from e

        try:
            data = json.loads(result.stdout)
            return Track(
                source_url=url,
                youtube_title=data.get("title", ""),
                youtube_artist=data.get("uploader", ""),
                youtube_duration=float(data.get("duration", 0.0)),
            )
        except json.JSONDecodeError as e:
            raise DownloadError("Failed to parse yt-dlp JSON output.") from e

    async def download_audio(
        self,
        url: str,
        output_dir: Path,
        quality: DownloadQuality = DownloadQuality.BEST,
    ) -> AsyncIterator[DownloadProgress | Path]:
        """Download audio from YouTube and yield progress.

        Args:
            url: YouTube URL.
            output_dir: Directory to save the file.
            quality: Desired audio quality.

        Yields:
            DownloadProgress events during download.
            Finally, yields the Path to the downloaded file.

        Raises:
            DownloadError: If download fails.
        """
        # We download the best audio format and let FFmpeg handle the conversion later.
        # We don't use yt-dlp's --extract-audio here because we want fine-grained
        # control over the FFmpeg conversion step and progress emitting in the pipeline.
        output_template = str(output_dir / "%(title)s [%(id)s].%(ext)s")

        cmd = [
            self.binary_path,
            "-f", "bestaudio/best",
            "--no-playlist",
            "--newline",  # Crucial for parsing progress line-by-line
            "-o", output_template,
        ] + self._get_cookies_args() + [url]

        logger.info(f"Starting download: {url}")

        final_path_str = None

        try:
            async for _stream_name, line in ProcessRunner.run_stream(cmd, check=True):
                # Check for the destination file path
                if "[download] Destination:" in line:
                    final_path_str = line.split("Destination:")[1].strip()
                elif "[download]" in line and "has already been downloaded" in line:
                    final_path_str = line.split("[download]")[1].split("has already")[0].strip()

                # Parse progress
                match = PROGRESS_REGEX.search(line)
                if match:
                    percent_str = match.group("percent")
                    speed = match.group("speed") or ""
                    try:
                        percent = float(percent_str)
                        yield DownloadProgress(percent=percent, speed=speed)
                    except ValueError:
                        pass
        except ProcessExecutionError as e:
            raise self._map_error(e) from e

        if not final_path_str:
            raise DownloadError("yt-dlp succeeded but output file path could not be determined.")

        output_path = Path(final_path_str)
        if not output_path.exists():
            raise DownloadError(f"yt-dlp reported output to {output_path}, but file does not exist.")

        yield output_path
