"""Tests for the exception hierarchy."""

from yt2ipod.core.models.errors import (
    ArtworkError,
    CleanupError,
    ConversionError,
    DependencyError,
    DeviceError,
    DownloadError,
    MetadataError,
    TransferError,
    Yt2IpodError,
)


class TestExceptionHierarchy:
    """All custom exceptions inherit from Yt2IpodError."""

    def test_base_error(self):
        err = Yt2IpodError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.cause is None

    def test_error_with_cause(self):
        cause = ConnectionError("Network unreachable")
        err = DownloadError("Download failed", cause=cause)
        assert err.cause is cause
        assert "caused by" in str(err)
        assert "Network unreachable" in str(err)

    def test_all_errors_are_yt2ipod_errors(self):
        errors = [
            DownloadError("test"),
            ConversionError("test"),
            MetadataError("test"),
            ArtworkError("test"),
            DeviceError("test"),
            TransferError("test"),
            CleanupError("test"),
            DependencyError("test"),
        ]
        for err in errors:
            assert isinstance(err, Yt2IpodError)
            assert isinstance(err, Exception)

    def test_all_errors_are_catchable_as_base(self):
        try:
            raise DownloadError("test")
        except Yt2IpodError as e:
            assert e.message == "test"

    def test_download_error(self):
        err = DownloadError("HTTP 429 Too Many Requests")
        assert "429" in str(err)

    def test_conversion_error(self):
        err = ConversionError("FFmpeg returned exit code 1")
        assert "FFmpeg" in str(err)

    def test_metadata_error(self):
        err = MetadataError("No MusicBrainz match found")
        assert "MusicBrainz" in str(err)


class TestDependencyError:
    """DependencyError has extra fields for install hints."""

    def test_with_install_hint(self):
        err = DependencyError(
            message="Missing dependency: ffmpeg",
            dependency="ffmpeg",
            install_hint="brew install ffmpeg",
        )
        assert err.dependency == "ffmpeg"
        assert err.install_hint == "brew install ffmpeg"
        result = str(err)
        assert "Missing dependency: ffmpeg" in result
        assert "brew install ffmpeg" in result

    def test_without_install_hint(self):
        err = DependencyError(
            message="Missing dependency: yt-dlp",
            dependency="yt-dlp",
        )
        assert "yt-dlp" in str(err)
        assert "Install it using" not in str(err)

    def test_with_cause(self):
        cause = FileNotFoundError("No such file: ffmpeg")
        err = DependencyError(
            message="ffmpeg not found",
            dependency="ffmpeg",
            install_hint="apt install ffmpeg",
            cause=cause,
        )
        assert err.cause is cause
        result = str(err)
        assert "ffmpeg not found" in result
        assert "apt install ffmpeg" in result
        assert "caused by" in result
