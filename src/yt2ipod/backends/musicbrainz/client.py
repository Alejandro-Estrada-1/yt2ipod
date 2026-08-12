"""MusicBrainz API client.

Uses the standard library (urllib) wrapped in asyncio.to_thread to maintain
zero external dependencies while remaining asynchronous. Implements a scoring
algorithm to find the best album match for a given track.

Centralizes rate limiting (1 request per second per MusicBrainz policy)
and User-Agent configuration.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from typing import Any, Dict, List

from yt2ipod import __app_name__, __version__
from yt2ipod.core.models.errors import MetadataError
from yt2ipod.core.models.track import Track, TrackMetadata
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://musicbrainz.org/ws/2"

# Allowed duration difference in milliseconds
MAX_DURATION_DIFF_MS = 20000  # 20 seconds


def _build_artist_credit_string(artist_credit: List[Dict[str, Any]]) -> str:
    """Concatenate all artist credits with their joinphrases.

    MusicBrainz artist-credit is a list like:
        [{"name": "Little Jesus", "joinphrase": ", "},
         {"name": "Ximena Sariñana", "joinphrase": ", "},
         {"name": "Elsa y Elmar"}]

    This produces: "Little Jesus, Ximena Sariñana, Elsa y Elmar"
    """
    if not artist_credit:
        return ""
    parts: list[str] = []
    for entry in artist_credit:
        name = entry.get("name", "")
        if not name:
            # Fallback to nested artist object
            artist_obj = entry.get("artist", {})
            name = artist_obj.get("name", "")
        parts.append(name)
        joinphrase = entry.get("joinphrase", "")
        if joinphrase:
            parts.append(joinphrase)
    return "".join(parts)


def _extract_artist_id(artist_credit: List[Dict[str, Any]]) -> str:
    """Extract the primary artist ID from artist credits."""
    if not artist_credit:
        return ""
    first = artist_credit[0]
    artist_obj = first.get("artist", {})
    return artist_obj.get("id", "")


def _similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
    a_n = a.lower().strip()
    b_n = b.lower().strip()
    if a_n == b_n:
        return 1.0
    return SequenceMatcher(None, a_n, b_n).ratio()


class MusicBrainzClient:
    """Client for querying the MusicBrainz API.

    All HTTP requests go through this client, which enforces:
    - A configurable User-Agent (required by MusicBrainz)
    - Rate limiting (1 request per second by default)
    - Retry logic for transient failures

    No other module should make direct HTTP requests to MusicBrainz.
    """

    def __init__(
        self,
        app_name: str = __app_name__,
        version: str = __version__,
        contact_url: str = "https://github.com/yt2ipod/yt2ipod",
        rate_limit_seconds: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        self.user_agent = f"{app_name}/{version} ({contact_url})"
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self._last_request_time: float = 0.0
        self._rate_lock = asyncio.Lock()

    def _enforce_rate_limit(self) -> None:
        """Block until at least rate_limit_seconds since last request."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        wait = self.rate_limit_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _sync_get(self, url: str) -> Dict[str, Any]:
        """Synchronous HTTP GET using urllib with rate limiting.

        Args:
            url: The full URL to fetch.

        Returns:
            Parsed JSON dictionary.

        Raises:
            MetadataError: On HTTP or parsing errors.
        """
        self._enforce_rate_limit()

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
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
        """Asynchronous wrapper for _sync_get.

        Uses asyncio.Lock to serialize requests (MusicBrainz requires
        at most 1 request per second per application).
        """
        async with self._rate_lock:
            return await asyncio.to_thread(self._sync_get, url)

    async def search_recordings(self, title: str, artist: str) -> List[Dict[str, Any]]:
        """Search for a recording by title and artist.

        Args:
            title: Track title.
            artist: Track artist.

        Returns:
            List of recording dictionaries.
        """
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

    async def get_recording(self, recording_id: str, inc: str = "releases+artists") -> Dict[str, Any]:
        """Fetch full recording details by ID.

        Args:
            recording_id: MusicBrainz recording UUID.
            inc: Sub-queries to include.

        Returns:
            Recording dictionary with included data.
        """
        encoded_id = urllib.parse.quote(recording_id)
        url = f"{BASE_URL}/recording/{encoded_id}?inc={inc}&fmt=json"
        return await self._async_get(url)

    async def get_release(self, release_id: str, inc: str = "artists+labels+media+release-groups") -> Dict[str, Any]:
        """Fetch full release details by ID.

        Args:
            release_id: MusicBrainz release UUID.
            inc: Sub-queries to include.

        Returns:
            Release dictionary with included data.
        """
        encoded_id = urllib.parse.quote(release_id)
        url = f"{BASE_URL}/release/{encoded_id}?inc={inc}&fmt=json"
        return await self._async_get(url)

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
                score -= 150  # Huge penalty for duration mismatch
            else:
                score -= int(diff)  # Small penalty for minor differences

        # 2. Title similarity bonus
        title_sim = _similarity(recording.get("title", ""), track.youtube_title)
        score += int(title_sim * 20)

        # 3. Artist similarity bonus
        rec_artist = _build_artist_credit_string(recording.get("artist-credit", []))
        artist_sim = _similarity(rec_artist, track.youtube_artist)
        score += int(artist_sim * 15)

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
            if status in ("Bootleg", "Promotion"):
                rel_score -= 50

            if rel_score > best_release_score:
                best_release_score = rel_score

                # Extract track position from media
                media = release.get("media", [{}])[0]
                track_list = media.get("track", [])
                track_data = track_list[0] if track_list else {}

                # Parse track number — MB returns it as a string
                raw_number = track_data.get("number")
                track_number: int | None = None
                if raw_number is not None:
                    try:
                        track_number = int(raw_number)
                    except (ValueError, TypeError):
                        track_number = None

                track_total = media.get("track-count")

                # Build full artist string from all credits with joinphrase
                recording_artist_credit = recording.get("artist-credit", [])
                artist_name = _build_artist_credit_string(recording_artist_credit)

                # Album artist: from the release credits (primary artist only)
                release_artist_credit = release.get("artist-credit", [])
                album_artist_name = _build_artist_credit_string(release_artist_credit) or artist_name

                # Extract artist IDs
                recording_artist_id = _extract_artist_id(recording_artist_credit)

                # Build list of all release IDs from this recording
                all_ids = [r.get("id") for r in releases if r.get("id")]

                best_meta = TrackMetadata(
                    title=recording.get("title", ""),
                    artist=artist_name,
                    album=release.get("title", ""),
                    album_artist=album_artist_name,
                    track_number=track_number,
                    track_total=track_total,
                    date=release.get("date", "")[:4] if release.get("date") else "",
                    musicbrainz_recording_id=recording.get("id", ""),
                    musicbrainz_release_id=release.get("id", ""),
                    musicbrainz_artist_id=recording_artist_id,
                    all_release_ids=all_ids,
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
        clean_title = track.youtube_title
        
        # Remove any parentheses or brackets at the end of the title recursively
        while True:
            new_title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*$', '', clean_title).strip()
            if new_title == clean_title or not new_title:
                break
            clean_title = new_title

        # Also remove common keywords anywhere in the title inside parentheses
        clean_title = re.sub(r'\s*[\(\[][^\)\]]*(?:lyrics|letra|video|audio|official|oficial|hq|hd|live|vivo)[^\)\]]*[\)\]]', '', clean_title, flags=re.IGNORECASE).strip()

        clean_artist = track.youtube_artist.replace("- Topic", "").strip()

        # If title contains ' - ', try to split artist and title to clean up the query
        if " - " in clean_title:
            parts = clean_title.split(" - ", 1)
            candidate_artist = parts[0].strip()
            candidate_title = parts[1].strip()
            
            # Use split title if the prefix matches our artist name
            if _similarity(candidate_artist, clean_artist) > 0.7 or clean_artist.lower() in candidate_artist.lower() or candidate_artist.lower() in clean_artist.lower():
                clean_title = candidate_title

        # Final cleanup of dots, punctuation and trailing noise for search query
        clean_title = clean_title.replace("...", "").replace("..", "")
        # Remove special characters that Lucene query parser might disallow or fail on
        clean_title = re.sub(r'[\\/*?:|"<>`~!\(\)\[\]\{\}\^~\-_]', ' ', clean_title)
        # Collapse multiple spaces
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()

        recordings = await self.search_recordings(clean_title, clean_artist)
        
        # Fallback 1: If no recordings found and YouTube title has ' - ',
        # the true artist might be written in the video title instead of the channel uploader.
        if not recordings and " - " in track.youtube_title:
            raw_title = track.youtube_title
            for suffix in ["(Official Video)", "[Official Audio]", "(Lyric Video)", "[Audio]",
                            "(Official Music Video)", "(Audio)", "[Official Video]",
                            "(Video Oficial)", "(Lyric)", "(Lyrics)", "(Audio Oficial)",
                            "Video Oficial", "Audio Oficial", "Letra", "Lyrics", " (Letra)", " (Lyrics)"]:
                raw_title = raw_title.replace(suffix, "").strip()
            
            raw_title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', raw_title).strip()
            parts = [p.strip() for p in raw_title.split(" - ") if p.strip()]
            
            if len(parts) >= 2:
                # Try parts[-2] as artist and parts[-1] as title
                fallback_artist = parts[-2]
                fallback_title = parts[-1]
                
                # Cleanup title for Lucene
                fallback_title_clean = fallback_title.replace("...", "").replace("..", "")
                fallback_title_clean = re.sub(r'[\\/*?:|"<>`~!\(\)\[\]\{\}\^~\-_]', ' ', fallback_title_clean)
                fallback_title_clean = re.sub(r'\s+', ' ', fallback_title_clean).strip()
                
                logger.info(f"Fallback search: recording='{fallback_title_clean}', artist='{fallback_artist}'")
                recordings = await self.search_recordings(fallback_title_clean, fallback_artist)
                
                # Try parts[0] as artist and parts[1] as title if we have 3 parts
                if not recordings and len(parts) >= 3:
                    fallback_artist = parts[0]
                    fallback_title = parts[1]
                    fallback_title_clean = fallback_title.replace("...", "").replace("..", "")
                    fallback_title_clean = re.sub(r'[\\/*?:|"<>`~!\(\)\[\]\{\}\^~\-_]', ' ', fallback_title_clean)
                    fallback_title_clean = re.sub(r'\s+', ' ', fallback_title_clean).strip()
                    
                    logger.info(f"Second fallback search: recording='{fallback_title_clean}', artist='{fallback_artist}'")
                    recordings = await self.search_recordings(fallback_title_clean, fallback_artist)

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
