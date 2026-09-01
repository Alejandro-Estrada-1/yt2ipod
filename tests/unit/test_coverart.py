import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip this entire module if Pillow is not installed
pytest.importorskip("PIL")

from PIL import Image

from yt2ipod.backends.coverartarchive.client import CoverArtArchiveClient
from yt2ipod.core.models.errors import DependencyError


class DummyCoverArtArchiveClient(CoverArtArchiveClient):
    """Subclass that bypasses the actual network calls."""

    def _sync_get_json(self, url: str) -> dict:
        return {
            "images": [
                {
                    "front": True,
                    "image": "https://example.org/cover-front.jpg"
                },
                {
                    "front": False,
                    "image": "https://example.org/cover-back.jpg"
                }
            ]
        }

    def _sync_download_image(self, url: str) -> bytes:
        # Create a non-square 800x600 mock image
        img = Image.new("RGB", (800, 600), color=(120, 200, 100))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()


@pytest.mark.asyncio
async def test_fetch_front_artwork_crops_and_resizes(tmp_path):
    client = DummyCoverArtArchiveClient()
    output_file = tmp_path / "artwork.jpg"

    artwork = await client.fetch_front_artwork(
        release_id="rel-12345",
        release_title="Río salvaje",
        output_path=output_file
    )

    assert artwork is not None
    assert artwork.is_valid is True
    assert artwork.is_downloaded is True
    assert artwork.width == 500
    assert artwork.height == 500
    assert artwork.format == "jpeg"
    assert artwork.release_id == "rel-12345"
    assert artwork.release_title == "Río salvaje"
    assert artwork.url == "https://example.org/cover-front.jpg"
    assert artwork.path == output_file

    # Load file from disk and check dimensions are 500x500
    saved_img = Image.open(output_file)
    assert saved_img.format == "JPEG"
    assert saved_img.size == (500, 500)


@pytest.mark.asyncio
async def test_dependency_missing_raises_error(tmp_path):
    client = CoverArtArchiveClient()
    
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name.startswith("PIL"):
            raise ImportError("mocked import error")
        return original_import(name, *args, **kwargs)
        
    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(DependencyError) as exc:
            await client.check_dependency()
            
    assert "Pillow is not installed" in str(exc.value)

