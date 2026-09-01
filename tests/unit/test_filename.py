"""Unit tests for the filename sanitization utility."""

from yt2ipod.utils.filename import sanitize_filename


def test_sanitize_clean_name():
    assert sanitize_filename("Normal Song Name") == "Normal Song Name"


def test_sanitize_dirty_name():
    assert sanitize_filename("Song: The Movie? *Great*") == "Song_ The Movie_ _Great_"


def test_sanitize_empty_fallback():
    assert sanitize_filename("") == "unnamed_track"
    assert sanitize_filename("   ") == "unnamed_track"
    assert sanitize_filename(' / \\ : * ? " < > | ') == "_ _ _ _ _ _ _ _ _"
