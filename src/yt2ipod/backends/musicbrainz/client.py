"""MusicBrainz API client.

Uses the standard library (urllib) wrapped in asyncio.to_thread to maintain
zero external dependencies while remaining asynchronous. Implements a scoring
algorithm to find the best album match for a given track.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from yt2ipod import __version__
from yt2ipod.core.models.errors import MetadataError
from yt2ipod.core.models.track import Track, TrackMetadata
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)

USER_AGENT = f"yt2ipod/{__version__} ( https://github.com/yt2ipod/yt2ipod )"
BASE_URL = "https://musicbrainz.org/ws/2"

# Allowed duration difference in milliseconds
MAX_DURATION_DIFF_MS = 20000  # 20 seconds


class MusicBrainzClient:
    """Client for querying the MusicBrainz API."""

    def _sync_get(self, url: str) -> Dict[str, Any]:
        """Synchronous HTTP GET using urllib.

        Args:
            url: The full URL to fetch.

        Returns:
            Parsed JSON dictionary.

        Raises:
            MetadataError: On HTTP or parsing errors.
        """
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 503:
                raise MetadataError("MusicBrainz rate limit exceeded (HTTP 503).") from e
            raise MetadataError(f"MusicBrainz API error: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise MetadataError(f"Network error connecting to MusicBrainz: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise MetadataError("Failed to parse MusicBrainz JSON response.") from e

    async def _async_get(self, url: str) -> Dict[str, Any]:
        """Asynchronous wrapper for _sync_get."""
        return await asyncio.to_thread(self._sync_get, url)

    async def search_recordings(self, title: str, artist: str) -> List[Dict[str, Any]]:
        """Search for a recording by title and artist.

        Args:
            title: Track title.
            artist: Track artist.

        Returns:
            List of recording dictionaries.
        """
        # Lucene query syntax
        query = f'recording:"{title}" AND artist:"{artist}"'
        params = {
            "query": query,
            "fmt": "json",
            "limit": "15",
        }
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/recording/?{query_string}"
        
        logger.debug(f"MusicBrainz search: {url}")
        
        data = await self._async_get(url)
        return data.get("recordings", [])

    def _score_release(self, recording: Dict[str, Any], track: Track) -> tuple[int, TrackMetadata | None]:
        """Score a recording/release match. Higher is better.

        Returns:
            Tuple of (score, TrackMetadata) or (0, None) if completely invalid.
        """
        score = 100
        
        # 1. Duration check
        mb_length = recording.get("length")
        if mb_length and track.youtube_duration > 0:
            mb_duration_sec = mb_length / 1000.0
            diff = abs(mb_duration_sec - track.youtube_duration)
            if diff > (MAX_DURATION_DIFF_MS / 1000.0):
                score -= 150  # Huge penalty for duration mismatch (e.g. Radio Edit vs Extended)
            else:
                score -= int(diff)  # Small penalty for minor differences

        releases = recording.get("releases", [])
        if not releases:
            return 0, None

        best_meta = None
        best_release_score = -1000

        for release in releases:
            rel_score = score
            
            # Prefer primary types
            rg = release.get("release-group", {})
            primary_type = rg.get("primary-type", "")
            secondary_types = rg.get("secondary-types", [])
            status = release.get("status", "")
            
            if primary_type == "Album":
                rel_score += 50
            elif primary_type == "Single":
                rel_score += 10
            elif primary_type == "EP":
                rel_score += 20
                
            # Penalize compilations, live, bootlegs
            if "Compilation" in secondary_types:
                rel_score -= 30
            if "Live" in secondary_types:
                rel_score -= 40
            if status == "Bootleg" or status == "Promotion":
                rel_score -= 50

            if rel_score > best_release_score:
                best_release_score = rel_score
                
                # Extract metadata
                media = release.get("media", [{}])[0]
                tracks = media.get("track", [{}])
                track_data = tracks[0] if tracks else {}
                
                # Use artist credit from the recording if available, else fallback
                artist_credit = recording.get("artist-credit", [])
                artist_name = artist_credit[0].get("name", "") if artist_credit else ""
                
                album_artist_credit = release.get("artist-credit", [])
                album_artist_name = album_artist_credit[0].get("name", "") if album_artist_credit else artist_name

                best_meta = TrackMetadata(
                    title=recording.get("title", ""),
                    artist=artist_name,
                    album=release.get("title", ""),
                    album_artist=album_artist_name,
                    track_number=track_data.get("number"),
                    track_total=media.get("track-count"),
                    date=release.get("date", "")[:4] if release.get("date") else "", # Just year
                    musicbrainz_recording_id=recording.get("id", ""),
                    musicbrainz_release_id=release.get("id", ""),
                )

        return best_release_score, best_meta

    async def match_track(self, track: Track) -> tuple[float, TrackMetadata | None]:
        """Find the best metadata match for a track.

        Args:
            track: The track to match. Must have youtube_title and youtube_artist.

        Returns:
            Tuple of (confidence_score, TrackMetadata). Confidence is 0.0 to 1.0.
            Returns (0.0, None) if no match found.
        """
        # Clean up title/artist for search
        # Strip common youtube suffixes like (Official Video), [Audio], etc.
        clean_title = track.youtube_title
        for suffix in ["(Official Video)", "[Official Audio]", "(Lyric Video)", "[Audio]"]:
            clean_title = clean_title.replace(suffix, "").strip()
            
        clean_artist = track.youtube_artist.replace("- Topic", "").strip()

        recordings = await self.search_recordings(clean_title, clean_artist)
        if not recordings:
            return 0.0, None

        best_score = -9999
        best_meta = None

        for recording in recordings:
            score, meta = self._score_release(recording, track)
            if meta and score > best_score:
                best_score = score
                best_meta = meta

        if not best_meta:
            return 0.0, None

        # Normalize confidence roughly (150 is a perfect album match)
        confidence = max(0.0, min(1.0, (best_score + 50) / 200.0))
        
        return confidence, best_meta
