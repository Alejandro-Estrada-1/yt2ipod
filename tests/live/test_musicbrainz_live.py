"""Live integration tests for the MusicBrainz backend."""

import pytest

from yt2ipod.backends.musicbrainz.client import MusicBrainzClient
from yt2ipod.core.models.errors import MetadataError
from yt2ipod.core.models.track import Track


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_match_track():
    """Test fetching metadata for a known track (TQM by Little Jesus).

    MusicBrainz enforces a strict 1 request per second rate limit,
    so this test might fail with a 503 if we are running in CI
    and multiple tests hit it simultaneously.
    """
    client = MusicBrainzClient()
    track = Track(
        youtube_title="TQM",
        youtube_artist="Little Jesus",
        youtube_duration=319.0,
    )
    
    try:
        confidence, meta = await client.match_track(track)
    except MetadataError as e:
        pytest.xfail(f"MusicBrainz API error (expected under rate limits): {e}")

    assert meta is not None
    assert confidence > 0.5
    
    # Verify the extracted metadata
    assert "Río salvaje" in meta.album
    assert "Little Jesus" in meta.album_artist
    assert meta.date.startswith("2016")
    
    # Track 2 on Rio Salvaje
    assert str(meta.track_number) == "2"
