"""Unit tests for the MusicBrainz client."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from yt2ipod.backends.musicbrainz.client import MusicBrainzClient
from yt2ipod.core.models.errors import MetadataError
from yt2ipod.core.models.track import Track


@pytest.fixture
def client():
    return MusicBrainzClient()


def create_mock_response(data: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


class TestMusicBrainzClient:
    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_search_recordings_success(self, mock_urlopen, client):
        mock_data = {
            "recordings": [
                {"id": "123", "title": "Test Song"}
            ]
        }
        mock_urlopen.return_value = create_mock_response(mock_data)
        
        results = await client.search_recordings("Test Song", "Test Artist")
        
        assert len(results) == 1
        assert results[0]["id"] == "123"
        
        # Verify user agent was sent
        req = mock_urlopen.call_args[0][0]
        assert "yt2ipod" in req.headers["User-agent"]

    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_rate_limit_error(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)
        
        with pytest.raises(MetadataError) as exc:
            await client.search_recordings("Test", "Artist")
            
        assert "rate limit exceeded" in str(exc.value).lower()

    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_match_track_scoring(self, mock_urlopen, client):
        # We simulate a recording with two releases: a compilation and a proper album
        mock_data = {
            "recordings": [
                {
                    "id": "rec1",
                    "title": "TQM",
                    "length": 319000,  # 319 seconds
                    "artist-credit": [{"name": "Little Jesus"}],
                    "releases": [
                        {
                            "id": "rel-comp",
                            "title": "Indie Hits 2016",
                            "status": "Official",
                            "release-group": {
                                "primary-type": "Album",
                                "secondary-types": ["Compilation"]
                            }
                        },
                        {
                            "id": "rel-album",
                            "title": "Rio Salvaje",
                            "status": "Official",
                            "date": "2016-05-13",
                            "release-group": {
                                "primary-type": "Album"
                            },
                            "media": [{
                                "track-count": 10,
                                "tracks": [{"number": "2"}]
                            }]
                        }
                    ]
                }
            ]
        }
        mock_urlopen.return_value = create_mock_response(mock_data)
        
        track = Track(youtube_title="TQM", youtube_artist="Little Jesus", youtube_duration=319.0)
        
        confidence, meta = await client.match_track(track)
        
        assert meta is not None
        assert confidence > 0.5
        # It should have picked the Album over the Compilation
        assert meta.album == "Rio Salvaje"
        assert meta.date == "2016"
        assert meta.track_number == "2"
        assert meta.track_total == 10

    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_match_track_duration_penalty(self, mock_urlopen, client):
        # We simulate a track that is a radio edit (150s) but the matched release is 319s
        mock_data = {
            "recordings": [
                {
                    "id": "rec1",
                    "title": "TQM",
                    "length": 319000,  # 319 seconds
                    "releases": [
                        {
                            "id": "rel1",
                            "title": "Rio Salvaje",
                            "release-group": {"primary-type": "Album"}
                        }
                    ]
                }
            ]
        }
        mock_urlopen.return_value = create_mock_response(mock_data)
        
        # User downloaded a short version
        track = Track(youtube_title="TQM", youtube_artist="Little Jesus", youtube_duration=150.0)
        
        confidence, meta = await client.match_track(track)
        
        assert meta is not None
        # Confidence should be extremely low because of the >20s duration difference penalty (-80)
        assert confidence < 0.4
