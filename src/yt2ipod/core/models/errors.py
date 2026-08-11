"""Custom exception hierarchy for yt2ipod.

All exceptions inherit from Yt2IpodError and provide
human-readable messages. Tracebacks are only shown in debug mode.
"""

from __future__ import annotations


class Yt2IpodError(Exception):
    """Base exception for all yt2ipod errors.

    Args:
        message: Human-readable error description.
        cause: Original exception that caused this error, if any.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        self.message = message
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        if self.cause:
            return f"{self.message} (caused by: {self.cause})"
        return self.message


class DownloadError(Yt2IpodError):
    """Error during YouTube download.

    Covers: HTTP 429, bot detection, authentication required,
    missing format, network errors, yt-dlp failures.
    """
    pass


class ConversionError(Yt2IpodError):
    """Error during audio conversion (FFmpeg)."""
    pass


class MetadataError(Yt2IpodError):
    """Error during MusicBrainz metadata identification."""
    pass


class ArtworkError(Yt2IpodError):
    """Error during Cover Art Archive artwork retrieval."""
    pass


class DeviceError(Yt2IpodError):
    """Error during device detection or communication."""
    pass


class TransferError(Yt2IpodError):
    """Error during file transfer to device."""
    pass


class CleanupError(Yt2IpodError):
    """Error during temporary file cleanup."""
    pass

class ProcessExecutionError(Yt2IpodError):
    """Error when a subprocess exits with a non-zero code.

    Args:
        message: Human-readable error description.
        exit_code: The non-zero exit code.
        stdout: Standard output of the process.
        stderr: Standard error of the process.
    """

    def __init__(
        self,
        message: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message)


class ProcessTimeoutError(Yt2IpodError):
    """Error when a subprocess exceeds the configured timeout."""
    pass


class DependencyError(Yt2IpodError):
    """Error when a required external dependency is missing.

    Example: ffmpeg not installed, yt-dlp not found.
    Should include platform-specific installation instructions.
    """

    def __init__(
        self,
        message: str,
        dependency: str = "",
        install_hint: str = "",
        cause: Exception | None = None,
    ) -> None:
        self.dependency = dependency
        self.install_hint = install_hint
        super().__init__(message, cause)

    def __str__(self) -> str:
        parts = [self.message]
        if self.install_hint:
            parts.append(f"\nInstall it using:\n  {self.install_hint}")
        if self.cause:
            parts.append(f"(caused by: {self.cause})")
        return "\n".join(parts)
