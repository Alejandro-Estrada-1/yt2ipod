"""Tests for pipeline events."""

from yt2ipod.core.models.events import (
    ArtworkFound,
    ArtworkNotFound,
    ArtworkSearchStarted,
    CleanupCompleted,
    CleanupStarted,
    ConversionCompleted,
    ConversionProgress,
    ConversionStarted,
    DeviceDetected,
    DeviceNotFound,
    DownloadCompleted,
    DownloadProgress,
    DownloadStarted,
    MetadataMatched,
    MetadataNotFound,
    MetadataSearchStarted,
    PipelineEvent,
    TaggingCompleted,
    TaggingStarted,
    TransferCompleted,
    TransferFailed,
    TransferProgress,
    TransferStarted,
)


class TestEventCreation:
    """Test that all events can be created with their fields."""

    def test_download_started(self):
        event = DownloadStarted(url="https://youtu.be/abc", title="Test")
        assert event.url == "https://youtu.be/abc"
        assert event.title == "Test"

    def test_download_progress(self):
        event = DownloadProgress(percent=50.0, downloaded_bytes=1024, total_bytes=2048)
        assert event.percent == 50.0

    def test_download_completed(self):
        event = DownloadCompleted(title="TQM", duration=3.5, file_size=1024)
        assert event.title == "TQM"

    def test_conversion_started(self):
        event = ConversionStarted(source_format="webm", target_format="mp3")
        assert event.target_format == "mp3"

    def test_conversion_progress(self):
        event = ConversionProgress(percent=75.0)
        assert event.percent == 75.0

    def test_conversion_completed(self):
        event = ConversionCompleted(duration=2.0, output_size=5000)
        assert event.output_size == 5000

    def test_metadata_search_started(self):
        event = MetadataSearchStarted(artist="Little Jesus", title="La magia")
        assert event.artist == "Little Jesus"

    def test_metadata_matched(self):
        event = MetadataMatched(
            artist="Little Jesus",
            title="La magia",
            album="Río salvaje",
            recording_id="5306a0c7-6afe-4ffc-8db7-35eb26af042d",
            confidence=0.95,
        )
        assert event.album == "Río salvaje"
        assert event.confidence == 0.95

    def test_metadata_not_found(self):
        event = MetadataNotFound(artist="Unknown", title="Unknown", reason="No results")
        assert event.reason == "No results"

    def test_artwork_search_started(self):
        event = ArtworkSearchStarted(release_id="de647895-4f23-4be0-8622-bdd7472a9aa4")
        assert event.release_id.startswith("de647895")

    def test_artwork_found(self):
        event = ArtworkFound(width=500, height=500)
        assert event.width == 500

    def test_artwork_not_found(self):
        event = ArtworkNotFound(reason="No front cover")
        assert event.reason == "No front cover"

    def test_device_detected(self):
        event = DeviceDetected(
            model="iPod touch 5G",
            ios_version="9.3.5",
            connection="USB",
        )
        assert event.model == "iPod touch 5G"

    def test_device_not_found(self):
        event = DeviceNotFound()
        assert isinstance(event, PipelineEvent)

    def test_transfer_started(self):
        event = TransferStarted(method="AFC", file_count=2)
        assert event.file_count == 2

    def test_transfer_progress(self):
        event = TransferProgress(percent=80.0, current_file="TQM.mp3", files_completed=1, files_total=2)
        assert event.current_file == "TQM.mp3"

    def test_transfer_completed(self):
        event = TransferCompleted(method="AFC", files_transferred=2, duration=5.0)
        assert event.files_transferred == 2

    def test_transfer_failed(self):
        event = TransferFailed(method="SSH", error="Connection refused")
        assert event.error == "Connection refused"

    def test_cleanup_started(self):
        event = CleanupStarted(file_count=5)
        assert event.file_count == 5

    def test_cleanup_completed(self):
        event = CleanupCompleted(files_removed=5, bytes_freed=1024)
        assert event.bytes_freed == 1024

    def test_tagging_started(self):
        event = TaggingStarted()
        assert isinstance(event, PipelineEvent)

    def test_tagging_completed(self):
        event = TaggingCompleted(has_artwork=True, has_metadata=True)
        assert event.has_artwork


class TestEventImmutability:
    """Verify that events are frozen (immutable)."""

    def test_download_started_frozen(self):
        event = DownloadStarted(url="https://youtu.be/abc")
        try:
            event.url = "changed"  # type: ignore
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass  # Expected — frozen dataclass

    def test_metadata_matched_frozen(self):
        event = MetadataMatched(artist="Little Jesus", title="La magia")
        try:
            event.artist = "changed"  # type: ignore
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass


class TestEventHierarchy:
    """Verify event inheritance."""

    def test_all_events_are_pipeline_events(self):
        events = [
            DownloadStarted(),
            DownloadProgress(),
            DownloadCompleted(),
            ConversionStarted(),
            ConversionCompleted(),
            MetadataSearchStarted(),
            MetadataMatched(),
            ArtworkSearchStarted(),
            ArtworkFound(),
            DeviceDetected(),
            TransferStarted(),
            TransferCompleted(),
            CleanupStarted(),
            CleanupCompleted(),
            TaggingStarted(),
            TaggingCompleted(),
        ]
        for event in events:
            assert isinstance(event, PipelineEvent), f"{type(event)} is not a PipelineEvent"
