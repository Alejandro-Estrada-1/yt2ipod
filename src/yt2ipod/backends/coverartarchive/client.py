"""Cover Art Archive client (Phase 6).

Fetches release artwork from the Cover Art Archive API and processes it
(crops/resizes to 500x500 square JPEG) using Pillow.
"""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict

from yt2ipod import __app_name__, __version__
from yt2ipod.core.models.artwork import Artwork
from yt2ipod.core.models.errors import DependencyError, MetadataError
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)

USER_AGENT = f"{__app_name__}/{__version__} ( https://github.com/yt2ipod/yt2ipod )"
BASE_URL = "https://coverartarchive.org/release"


class CoverArtArchiveClient:
    """Client for querying Cover Art Archive and downloading release artwork."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def check_dependency(self) -> None:
        """Verify that Pillow is installed.

        Raises:
            DependencyError: If Pillow is missing.
        """
        try:
            import PIL.Image  # noqa: F401
        except ImportError as e:
            raise DependencyError(
                "Pillow is not installed. Cover art features require Pillow.",
                dependency="Pillow",
                install_hint='pip install "yt2ipod[artwork]"',
            ) from e

    def _sync_get_json(self, url: str) -> Dict[str, Any]:
        """Fetch JSON from Cover Art Archive."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read()
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Cover Art Archive returns 404 if no cover art exists for the release
                logger.info(f"No cover art found for release URL: {url}")
                return {}
            raise MetadataError(f"Cover Art Archive API error: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise MetadataError(f"Network error connecting to Cover Art Archive: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise MetadataError("Failed to parse Cover Art Archive JSON response.") from e

    def _sync_download_image(self, url: str) -> bytes:
        """Download image bytes."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except Exception as e:
            raise MetadataError(f"Failed to download artwork image from {url}: {e}") from e

    def _sync_process_image(self, data: bytes, dest_path: Path) -> tuple[int, int, str]:
        """Crop, resize, and save image to a square 500x500 JPEG."""
        from PIL import Image

        try:
            img = Image.open(io.BytesIO(data))
        except Exception as e:
            raise MetadataError(f"Failed to parse image data: {e}") from e

        # Convert to RGB/JPEG
        img = img.convert("RGB")

        # Create a centered square crop
        width, height = img.size
        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        right = left + min_side
        bottom = top + min_side
        img = img.crop((left, top, right, bottom))

        # Resize to 500x500 using Lanczos filter
        img = img.resize((500, 500), Image.Resampling.LANCZOS)

        # Save to destination path
        try:
            img.save(dest_path, format="JPEG", quality=90)
        except Exception as e:
            raise MetadataError(f"Failed to save processed artwork to {dest_path}: {e}") from e

        return 500, 500, "jpeg"

    async def fetch_front_artwork(
        self, release_id: str, release_title: str, output_path: Path
    ) -> Artwork | None:
        """Fetch and process the front cover art for a release.

        Args:
            release_id: MusicBrainz release UUID.
            release_title: Release title (for metadata).
            output_path: Path to save the processed square JPEG.

        Returns:
            Artwork object, or None if no artwork is found/processed.
        """
        await self.check_dependency()

        encoded_id = urllib.parse.quote(release_id)
        url = f"{BASE_URL}/{encoded_id}"

        # Fetch release cover art list JSON
        meta = await asyncio.to_thread(self._sync_get_json, url)
        images = meta.get("images", [])
        if not images:
            return None

        # Find front image URL
        front_url = None
        for img in images:
            if img.get("front"):
                front_url = img.get("image")
                break

        # Fallback to the first image in list if no front image is explicitly marked
        if not front_url:
            front_url = images[0].get("image")

        if not front_url:
            return None

        # Download image bytes
        image_bytes = await asyncio.to_thread(self._sync_download_image, front_url)

        # Process image in a thread pool
        width, height, fmt = await asyncio.to_thread(
            self._sync_process_image, image_bytes, output_path
        )

        return Artwork(
            path=output_path,
            url=front_url,
            width=width,
            height=height,
            format=fmt,
            release_id=release_id,
            release_title=release_title,
        )
