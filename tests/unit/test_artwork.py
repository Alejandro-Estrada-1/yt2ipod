"""Tests for the Artwork model."""

from pathlib import Path

from yt2ipod.core.models.artwork import (
    ARTWORK_TARGET_HEIGHT,
    ARTWORK_TARGET_WIDTH,
    Artwork,
)


class TestArtwork:
    """Tests for Artwork dataclass."""

    def test_valid_artwork(self):
        art = Artwork(
            path=Path("/tmp/cover.jpg"),
            url="https://coverartarchive.org/...",
            width=500,
            height=500,
            format="jpeg",
            release_id="de647895-4f23-4be0-8622-bdd7472a9aa4",
            release_title="Río salvaje",
        )
        assert art.is_valid
        assert art.has_release_link
        assert art.dimensions_string == "500x500"

    def test_invalid_dimensions(self):
        art = Artwork(
            path=Path("/tmp/cover.jpg"),
            width=300,
            height=300,
            format="jpeg",
        )
        assert not art.is_valid

    def test_invalid_format(self):
        art = Artwork(
            path=Path("/tmp/cover.jpg"),
            width=500,
            height=500,
            format="html",
        )
        assert not art.is_valid

    def test_no_path(self):
        art = Artwork(
            width=500,
            height=500,
            format="jpeg",
        )
        assert not art.is_valid

    def test_png_format_valid(self):
        art = Artwork(
            path=Path("/tmp/cover.png"),
            width=500,
            height=500,
            format="png",
        )
        assert art.is_valid

    def test_no_release_link(self):
        art = Artwork()
        assert not art.has_release_link

    def test_target_constants(self):
        assert ARTWORK_TARGET_WIDTH == 500
        assert ARTWORK_TARGET_HEIGHT == 500

    def test_defaults(self):
        art = Artwork()
        assert art.path is None
        assert art.url == ""
        assert art.width == 0
        assert art.height == 0
        assert art.format == ""
        assert art.release_id == ""

    def test_non_square_invalid(self):
        """Non-square images should be invalid."""
        art = Artwork(
            path=Path("/tmp/cover.jpg"),
            width=500,
            height=400,
            format="jpeg",
        )
        assert not art.is_valid
