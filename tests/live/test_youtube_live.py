"""Live integration tests for the YouTube backend.

These tests require an active internet connection and the yt-dlp binary
installed on the system. They are marked with @pytest.mark.live and can
be skipped with `pytest -m "not live"`.
"""

import pytest

from yt2ipod.backends.youtube.client import YtDlpClient
from yt2ipod.core.models.errors import DownloadError


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_get_metadata():
    """Test fetching metadata for a known video (TQM by Little Jesus).

    Video ID: zYeteg4PxmU
    Expected duration: ~227 seconds
    """
    client = YtDlpClient()

    # Fast-fail if yt-dlp isn't installed
    await client.check_dependency()

    url = "https://youtu.be/zYeteg4PxmU"
    try:
        track = await client.get_metadata(url)
    except DownloadError as e:
        pytest.xfail(f"YouTube blocked the request (expected in CI environments): {e}")

    assert track.source_url == url
    assert "TQM" in track.youtube_title
    assert "Little Jesus" in track.youtube_artist

    # The TQM music video is ~319 seconds long
    assert 315 < track.youtube_duration < 325
