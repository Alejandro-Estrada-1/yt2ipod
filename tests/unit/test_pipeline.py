"""Unit tests for the Pipeline orchestrator."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yt2ipod.core.models import events
from yt2ipod.core.models.config import AppConfig
from yt2ipod.core.models.device import Device, DeviceCapabilities
from yt2ipod.core.models.track import TrackMetadata, AudioInfo
from yt2ipod.core.pipeline.orchestrator import Pipeline
from yt2ipod.core.transfer.manager import TransferResult


@pytest.fixture
def mock_downloader(tmp_path):
    from yt2ipod.core.models.track import Track
    dl = MagicMock()
    dl.check_dependency = AsyncMock()
    dl.get_metadata = AsyncMock(return_value=Track(
        youtube_title="La magia",
        youtube_artist="Little Jesus",
        youtube_duration=245.0
    ))
    
    async def mock_dl_audio(url, output_dir, *args, **kwargs):
        class Progress:
            percent = 50.0
            downloaded_bytes = 1000
            total_bytes = 2000
            speed = "100 KB/s"
        yield Progress()
        class DoneProgress:
            percent = 100.0
            downloaded_bytes = 2000
            total_bytes = 2000
            speed = "100 KB/s"
        yield DoneProgress()
        # yield a dummy file path
        dummy_file = output_dir / "downloaded_audio.mp3"
        dummy_file.write_text("dummy binary data")
        yield dummy_file

    dl.download_audio = mock_dl_audio
    return dl


@pytest.fixture
def mock_musicbrainz():
    mb = MagicMock()
    mb.match_track = AsyncMock(return_value=(
        0.95,
        TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            musicbrainz_recording_id="rec-123",
            musicbrainz_release_id="rel-456",
            musicbrainz_artist_id="art-789",
        )
    ))
    return mb


@pytest.fixture
def mock_coverart():
    ca = MagicMock()
    # returns an Artwork object or None
    mock_artwork = MagicMock()
    mock_artwork.is_valid = True
    mock_artwork.width = 500
    mock_artwork.height = 500
    mock_artwork.release_id = "rel-456"
    ca.fetch_front_artwork = AsyncMock(return_value=mock_artwork)
    return ca


@pytest.fixture
def mock_ffmpeg():
    ff = MagicMock()
    ff.check_dependency = AsyncMock()
    
    async def mock_convert(*args, **kwargs):
        class Progress:
            percent = 100.0
        yield Progress()

    ff.convert_to_mp3 = mock_convert
    ff.embed_metadata = AsyncMock()
    ff.probe = AsyncMock(return_value=AudioInfo(
        codec="mp3",
        sample_rate=44100,
        channels=2,
        duration=245.0,
        has_artwork=True
    ))
    return ff


@pytest.fixture
def mock_device_detector():
    det = MagicMock()
    det.detect_devices = AsyncMock(return_value=[
        Device(
            model="iPod Classic",
            ios_version="1.1.2",
            capabilities=DeviceCapabilities(usb=True, afc=True)
        )
    ])
    return det


@pytest.fixture
def mock_transfer_manager():
    tm = MagicMock()
    # transfer_files is async
    tm.transfer_files = AsyncMock(return_value=TransferResult(
        success=True,
        files_transferred=1,
        duration=1.5,
        method=MagicMock(value="afc")
    ))
    return tm


@pytest.mark.asyncio
async def test_pipeline_run_success(
    mock_downloader,
    mock_musicbrainz,
    mock_coverart,
    mock_ffmpeg,
    mock_device_detector,
    mock_transfer_manager,
    tmp_path,
):
    output_dir = tmp_path / "Output"
    
    pipeline = Pipeline(
        downloader=mock_downloader,
        musicbrainz=mock_musicbrainz,
        coverart=mock_coverart,
        ffmpeg=mock_ffmpeg,
        device_detector=mock_device_detector,
        transfer_manager=mock_transfer_manager,
    )
    
    emitted_events = []
    def callback(event):
        emitted_events.append(event)
        
    track = await pipeline.run(
        url_or_path="https://youtube.com/watch?v=lamagia",
        output_dir=output_dir,
        event_callback=callback,
        keep_temp=False,
        transfer=True
    )
    
    # Assert track final values
    assert track.output_path == output_dir / "La magia.mp3"
    assert track.metadata.album == "Río salvaje"
    assert track.audio_info.is_valid_mp3 is True
    
    # Assert events were emitted in correct order
    types = [type(e) for e in emitted_events]
    assert events.DownloadStarted in types
    assert events.DownloadProgress in types
    assert events.DownloadCompleted in types
    assert events.ConversionStarted in types
    assert events.ConversionProgress in types
    assert events.ConversionCompleted in types
    assert events.MetadataSearchStarted in types
    assert events.MetadataMatched in types
    assert events.ArtworkSearchStarted in types
    assert events.ArtworkFound in types
    assert events.TaggingStarted in types
    assert events.TaggingCompleted in types
    assert events.DeviceDetected in types
    assert events.TransferStarted in types
    assert events.TransferCompleted in types
    assert events.CleanupStarted in types
    assert events.CleanupCompleted in types


@pytest.mark.asyncio
async def test_pipeline_cover_art_fallback(
    mock_downloader,
    mock_musicbrainz,
    mock_coverart,
    mock_ffmpeg,
    mock_device_detector,
    mock_transfer_manager,
    tmp_path,
):
    output_dir = tmp_path / "Output"
    
    # Configure mock_musicbrainz to return multiple release IDs
    mock_musicbrainz.match_track = AsyncMock(return_value=(
        0.95,
        TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            musicbrainz_recording_id="rec-123",
            musicbrainz_release_id="rel-no-cover",
            musicbrainz_artist_id="art-789",
            all_release_ids=["rel-no-cover", "rel-with-cover"],
        )
    ))
    
    # Configure mock_coverart to return None for "rel-no-cover", and valid Artwork for "rel-with-cover"
    async def mock_fetch_front(rid, title, out_path):
        if rid == "rel-no-cover":
            return None
        elif rid == "rel-with-cover":
            mock_artwork = MagicMock()
            mock_artwork.is_valid = True
            mock_artwork.width = 500
            mock_artwork.height = 500
            mock_artwork.release_id = "rel-with-cover"
            return mock_artwork
        return None
        
    mock_coverart.fetch_front_artwork = mock_fetch_front

    pipeline = Pipeline(
        downloader=mock_downloader,
        musicbrainz=mock_musicbrainz,
        coverart=mock_coverart,
        ffmpeg=mock_ffmpeg,
        device_detector=mock_device_detector,
        transfer_manager=mock_transfer_manager,
    )
    
    track = await pipeline.run(
        url_or_path="https://youtube.com/watch?v=lamagia",
        output_dir=output_dir,
        event_callback=lambda x: None,
        keep_temp=False,
        transfer=False
    )
    
    # The final release_id must be updated to the one that actually had artwork
    assert track.metadata.musicbrainz_release_id == "rel-with-cover"
    assert track.artwork_path is not None


@pytest.mark.asyncio
async def test_pipeline_cover_art_deep_rescue(
    mock_downloader,
    mock_musicbrainz,
    mock_coverart,
    mock_ffmpeg,
    mock_device_detector,
    mock_transfer_manager,
    tmp_path,
):
    output_dir = tmp_path / "Output"
    
    # MusicBrainz match has only one release with no cover
    mock_musicbrainz.match_track = AsyncMock(return_value=(
        0.95,
        TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            musicbrainz_recording_id="rec-123",
            musicbrainz_release_id="rel-no-cover",
            musicbrainz_artist_id="art-789",
            all_release_ids=["rel-no-cover"],
        )
    ))
    
    # Mock detailed recording fetch to return historical release list
    mock_musicbrainz.get_recording = AsyncMock(return_value={
        "releases": [
            {"id": "rel-no-cover"},
            {"id": "rel-historical-cover-art"},
        ]
    })
    
    # Mock coverart to return artwork only for rel-historical-cover-art
    async def mock_fetch_front(rid, title, out_path):
        if rid == "rel-historical-cover-art":
            mock_artwork = MagicMock()
            mock_artwork.is_valid = True
            mock_artwork.width = 500
            mock_artwork.height = 500
            mock_artwork.release_id = "rel-historical-cover-art"
            return mock_artwork
        return None
        
    mock_coverart.fetch_front_artwork = mock_fetch_front

    pipeline = Pipeline(
        downloader=mock_downloader,
        musicbrainz=mock_musicbrainz,
        coverart=mock_coverart,
        ffmpeg=mock_ffmpeg,
        device_detector=mock_device_detector,
        transfer_manager=mock_transfer_manager,
    )
    
    track = await pipeline.run(
        url_or_path="https://youtube.com/watch?v=lamagia",
        output_dir=output_dir,
        event_callback=lambda x: None,
        keep_temp=False,
        transfer=False
    )
    
    assert track.metadata.musicbrainz_release_id == "rel-historical-cover-art"
    assert track.artwork_path is not None


@pytest.mark.asyncio
async def test_pipeline_cover_art_youtube_thumbnail_rescue(
    mock_downloader,
    mock_musicbrainz,
    mock_coverart,
    mock_ffmpeg,
    mock_device_detector,
    mock_transfer_manager,
    tmp_path,
):
    output_dir = tmp_path / "Output"
    
    # Configure mock_downloader to provide a youtube thumbnail URL
    from yt2ipod.core.models.track import Track as TrackModel
    mock_downloader.get_metadata = AsyncMock(return_value=TrackModel(
        youtube_title="La magia",
        youtube_artist="Little Jesus",
        youtube_duration=245.0,
        youtube_thumbnail_url="https://youtube.com/thumb.jpg"
    ))

    # MusicBrainz match has one release
    mock_musicbrainz.match_track = AsyncMock(return_value=(
        0.95,
        TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            musicbrainz_recording_id="rec-123",
            musicbrainz_release_id="rel-no-cover",
            musicbrainz_artist_id="art-789",
            all_release_ids=["rel-no-cover"],
        )
    ))
    
    # Detailed get_recording returns nothing new
    mock_musicbrainz.get_recording = AsyncMock(return_value={"releases": []})
    
    # CoverArt Archive mock fails (returns None) for all queries
    mock_coverart.fetch_front_artwork = AsyncMock(return_value=None)
    mock_coverart._sync_download_image = MagicMock(return_value=b"fake raw image bytes")
    mock_coverart._sync_process_image = MagicMock(return_value=(500, 500, "jpeg"))

    pipeline = Pipeline(
        downloader=mock_downloader,
        musicbrainz=mock_musicbrainz,
        coverart=mock_coverart,
        ffmpeg=mock_ffmpeg,
        device_detector=mock_device_detector,
        transfer_manager=mock_transfer_manager,
    )
    
    track = await pipeline.run(
        url_or_path="https://youtube.com/watch?v=lamagia",
        output_dir=output_dir,
        event_callback=lambda x: None,
        keep_temp=False,
        transfer=False
    )
    
    # Check that it downloaded and processed the YouTube thumbnail
    assert track.artwork_path is not None
    mock_coverart._sync_download_image.assert_called_once_with("https://youtube.com/thumb.jpg")
    mock_coverart._sync_process_image.assert_called_once()
