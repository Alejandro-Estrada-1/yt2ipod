"""Unit tests for the MusicBrainz client."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from yt2ipod.backends.musicbrainz.client import (
    MusicBrainzClient,
    _build_artist_credit_string,
    _extract_artist_id,
    _similarity,
)
from yt2ipod.core.models.errors import MetadataError
from yt2ipod.core.models.track import Track


@pytest.fixture
def client():
    # rate_limit_seconds=0 for fast tests
    return MusicBrainzClient(rate_limit_seconds=0.0)


def create_mock_response(data: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


class TestArtistCreditString:
    """Tests for _build_artist_credit_string — critical for multi-artist tracks."""

    def test_single_artist(self):
        credit = [{"name": "Little Jesus"}]
        assert _build_artist_credit_string(credit) == "Little Jesus"

    def test_multiple_artists_with_joinphrase(self):
        """TQM case: three artists with joinphrases."""
        credit = [
            {"name": "Little Jesus", "joinphrase": ", "},
            {"name": "Ximena Sariñana", "joinphrase": ", "},
            {"name": "Elsa y Elmar"},
        ]
        result = _build_artist_credit_string(credit)
        assert result == "Little Jesus, Ximena Sariñana, Elsa y Elmar"

    def test_fallback_to_artist_object(self):
        credit = [{"artist": {"id": "abc", "name": "Test Artist"}}]
        assert _build_artist_credit_string(credit) == "Test Artist"

    def test_empty_credit(self):
        assert _build_artist_credit_string([]) == ""


class TestExtractArtistId:
    def test_with_artist_object(self):
        credit = [{"artist": {"id": "abc-123", "name": "Little Jesus"}}]
        assert _extract_artist_id(credit) == "abc-123"

    def test_empty(self):
        assert _extract_artist_id([]) == ""


class TestSimilarity:
    def test_identical(self):
        assert _similarity("hello", "hello") == 1.0

    def test_case_insensitive(self):
        assert _similarity("Hello", "hello") == 1.0

    def test_different(self):
        assert _similarity("abc", "xyz") < 0.5

    def test_empty(self):
        assert _similarity("", "test") == 0.0


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
        """Test that album is preferred over compilation and track_number is int."""
        mock_data = {
            "recordings": [
                {
                    "id": "rec1",
                    "title": "TQM",
                    "length": 319000,
                    "artist-credit": [
                        {"name": "Little Jesus", "artist": {"id": "artist-lj", "name": "Little Jesus"}}
                    ],
                    "releases": [
                        {
                            "id": "rel-comp",
                            "title": "Indie Hits 2016",
                            "status": "Official",
                            "artist-credit": [{"name": "Various Artists"}],
                            "release-group": {
                                "primary-type": "Album",
                                "secondary-types": ["Compilation"]
                            }
                        },
                        {
                            "id": "rel-album",
                            "title": "Río salvaje",
                            "status": "Official",
                            "date": "2016-05-13",
                            "artist-credit": [
                                {"name": "Little Jesus", "artist": {"id": "artist-lj", "name": "Little Jesus"}}
                            ],
                            "release-group": {
                                "primary-type": "Album"
                            },
                            "media": [{
                                "track-count": 10,
                                "track": [{"number": "2"}]
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
        assert meta.album == "Río salvaje"
        assert meta.date == "2016"
        # track_number must be int, not string
        assert meta.track_number == 2
        assert isinstance(meta.track_number, int)
        assert meta.track_total == 10
        # Artist ID should be extracted
        assert meta.musicbrainz_artist_id == "artist-lj"

    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_multi_artist_credit_tqm(self, mock_urlopen, client):
        """TQM must preserve all artist credits with joinphrases."""
        mock_data = {
            "recordings": [
                {
                    "id": "rec-tqm",
                    "title": "TQM",
                    "length": 227000,
                    "artist-credit": [
                        {"name": "Little Jesus", "joinphrase": ", ",
                         "artist": {"id": "a1", "name": "Little Jesus"}},
                        {"name": "Ximena Sariñana", "joinphrase": ", ",
                         "artist": {"id": "a2", "name": "Ximena Sariñana"}},
                        {"name": "Elsa y Elmar",
                         "artist": {"id": "a3", "name": "Elsa y Elmar"}},
                    ],
                    "releases": [
                        {
                            "id": "rel-rio",
                            "title": "Río salvaje",
                            "status": "Official",
                            "date": "2016",
                            "artist-credit": [
                                {"name": "Little Jesus",
                                 "artist": {"id": "a1", "name": "Little Jesus"}}
                            ],
                            "release-group": {"primary-type": "Album"},
                            "media": [{"track-count": 10, "track": [{"number": "10"}]}]
                        }
                    ]
                }
            ]
        }
        mock_urlopen.return_value = create_mock_response(mock_data)

        track = Track(youtube_title="TQM", youtube_artist="Little Jesus", youtube_duration=227.0)
        confidence, meta = await client.match_track(track)

        assert meta is not None
        # Full artist credit with all names
        assert meta.artist == "Little Jesus, Ximena Sariñana, Elsa y Elmar"
        # Album artist is only the primary release artist
        assert meta.album_artist == "Little Jesus"
        # Both must NOT be the same (spec §28-29)
        assert meta.artist != meta.album_artist
        assert meta.track_number == 10
        assert meta.track_total == 10

    @pytest.mark.asyncio
    @patch("urllib.request.urlopen")
    async def test_match_track_duration_penalty(self, mock_urlopen, client):
        """Short version should get low confidence due to duration mismatch."""
        mock_data = {
            "recordings": [
                {
                    "id": "rec1",
                    "title": "TQM",
                    "length": 319000,
                    "artist-credit": [{"name": "Little Jesus"}],
                    "releases": [
                        {
                            "id": "rel1",
                            "title": "Río salvaje",
                            "artist-credit": [{"name": "Little Jesus"}],
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
        # Confidence should be low because of the >20s duration difference penalty
        assert confidence < 0.5

    def test_configurable_user_agent(self):
        """User agent must be configurable per spec §23."""
        client = MusicBrainzClient(
            app_name="myapp",
            version="1.2.3",
            contact_url="https://example.com",
            rate_limit_seconds=0.0,
        )
        assert client.user_agent == "myapp/1.2.3 (https://example.com)"

