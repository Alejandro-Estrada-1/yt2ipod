"""Tests for Track, TrackMetadata, and AudioInfo models.

Uses real values from the test cases:
- Little Jesus — TQM
- Little Jesus — La magia
"""

from pathlib import Path

from yt2ipod.core.models.track import AudioInfo, Track, TrackMetadata


class TestTrackMetadata:
    """Tests for TrackMetadata dataclass."""

    def test_create_la_magia(self):
        """La magia: single artist, standard metadata."""
        meta = TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            track_number=2,
            track_total=10,
            date="2016",
            genre="Alternative",
            musicbrainz_recording_id="5306a0c7-6afe-4ffc-8db7-35eb26af042d",
            musicbrainz_release_id="de647895-4f23-4be0-8622-bdd7472a9aa4",
        )
        assert meta.title == "La magia"
        assert meta.artist == "Little Jesus"
        assert meta.album_artist == "Little Jesus"
        assert meta.track_number == 2
        assert meta.track_total == 10
        assert meta.track_string == "2/10"
        assert meta.date == "2016"
        assert meta.has_musicbrainz_ids

    def test_create_tqm(self):
        """TQM: multiple artists (track credit != album artist)."""
        meta = TrackMetadata(
            title="TQM",
            artist="Little Jesus, Ximena Sariñana, Elsa y Elmar",
            album="Río salvaje",
            album_artist="Little Jesus",
            track_number=10,
            track_total=10,
            date="2016",
            genre="Alternative",
        )
        assert meta.title == "TQM"
        # Track artist includes all credited artists
        assert "Ximena Sariñana" in meta.artist
        assert "Elsa y Elmar" in meta.artist
        # Album artist remains the primary artist
        assert meta.album_artist == "Little Jesus"
        assert meta.track_string == "10/10"

    def test_artist_not_equal_album_artist(self):
        """Critical: artist and album_artist MUST be independent fields."""
        meta = TrackMetadata(
            artist="Little Jesus, Ximena Sariñana, Elsa y Elmar",
            album_artist="Little Jesus",
        )
        assert meta.artist != meta.album_artist

    def test_same_album_different_artists(self):
        """TQM and La magia must belong to the same album despite different artists."""
        tqm = TrackMetadata(
            title="TQM",
            artist="Little Jesus, Ximena Sariñana, Elsa y Elmar",
            album="Río salvaje",
            album_artist="Little Jesus",
        )
        la_magia = TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
        )
        # Same album and album_artist → same album in music player
        assert tqm.album == la_magia.album
        assert tqm.album_artist == la_magia.album_artist
        # But track artists differ
        assert tqm.artist != la_magia.artist

    def test_track_string_no_total(self):
        meta = TrackMetadata(track_number=5)
        assert meta.track_string == "5"

    def test_track_string_empty(self):
        meta = TrackMetadata()
        assert meta.track_string == ""

    def test_display_summary(self):
        meta = TrackMetadata(artist="Little Jesus", title="La magia")
        assert meta.display_summary() == "Little Jesus — La magia"

    def test_display_summary_empty(self):
        meta = TrackMetadata()
        assert meta.display_summary() == "(unknown track)"

    def test_no_musicbrainz_ids(self):
        meta = TrackMetadata(title="Test")
        assert not meta.has_musicbrainz_ids

    def test_defaults(self):
        meta = TrackMetadata()
        assert meta.title == ""
        assert meta.artist == ""
        assert meta.album == ""
        assert meta.album_artist == ""
        assert meta.track_number is None
        assert meta.track_total is None
        assert meta.date == ""
        assert meta.genre == ""
        assert meta.musicbrainz_recording_id == ""


class TestAudioInfo:
    """Tests for AudioInfo dataclass."""

    def test_duration_difference_excellent_match(self):
        """Real case: La magia local vs MusicBrainz — near-perfect match."""
        info = AudioInfo(duration=245.365)
        # MusicBrainz: 245373 ms
        diff = info.duration_difference_ms(245373)
        assert diff < 0.01  # < 10ms difference

    def test_duration_difference_ms(self):
        info = AudioInfo(duration=200.0)
        diff = info.duration_difference_ms(200000)  # 200.0 seconds
        assert diff == 0.0

    def test_duration_ms_property(self):
        info = AudioInfo(duration=245.365)
        assert info.duration_ms == 245365

    def test_valid_mp3(self):
        info = AudioInfo(
            codec="mp3",
            sample_rate=44100,
            channels=2,
            duration=245.0,
        )
        assert info.is_valid_mp3

    def test_invalid_mp3_wrong_codec(self):
        info = AudioInfo(codec="aac", sample_rate=44100, channels=2, duration=100.0)
        assert not info.is_valid_mp3

    def test_invalid_mp3_wrong_sample_rate(self):
        info = AudioInfo(codec="mp3", sample_rate=48000, channels=2, duration=100.0)
        assert not info.is_valid_mp3

    def test_invalid_mp3_mono(self):
        info = AudioInfo(codec="mp3", sample_rate=44100, channels=1, duration=100.0)
        assert not info.is_valid_mp3

    def test_invalid_mp3_zero_duration(self):
        info = AudioInfo(codec="mp3", sample_rate=44100, channels=2, duration=0.0)
        assert not info.is_valid_mp3

    def test_file_size_mb(self):
        info = AudioInfo(file_size=5 * 1024 * 1024)
        assert info.file_size_mb == 5.0

    def test_artwork_info(self):
        info = AudioInfo(has_artwork=True, artwork_width=500, artwork_height=500)
        assert info.has_artwork
        assert info.artwork_width == 500

    def test_defaults(self):
        info = AudioInfo()
        assert info.codec == ""
        assert info.sample_rate == 0
        assert info.channels == 0
        assert info.bitrate == 0
        assert info.duration == 0.0
        assert info.file_size == 0
        assert not info.has_artwork


class TestTrack:
    """Tests for Track dataclass."""

    def test_youtube_track(self):
        track = Track(
            source_url="https://youtu.be/zYeteg4PxmU",
            youtube_title="TQM",
            youtube_artist="Little Jesus",
            youtube_duration=227.0,
        )
        assert track.is_from_youtube
        assert not track.is_local_import
        assert "Little Jesus" in track.display_name

    def test_local_track(self):
        track = Track(
            source_path=Path("/music/song.mp3"),
        )
        assert track.is_local_import
        assert not track.is_from_youtube
        assert track.display_name == "song"

    def test_display_name_prefers_metadata(self):
        track = Track(
            youtube_title="TQM ft. blah",
            metadata=TrackMetadata(title="TQM", artist="Little Jesus"),
        )
        assert track.display_name == "Little Jesus — TQM"

    def test_display_name_fallback_url(self):
        track = Track(source_url="https://youtu.be/abc")
        assert track.display_name == "https://youtu.be/abc"

    def test_display_name_unknown(self):
        track = Track()
        assert track.display_name == "(unknown)"

    def test_track_with_full_data(self):
        meta = TrackMetadata(
            title="La magia",
            artist="Little Jesus",
            album="Río salvaje",
            album_artist="Little Jesus",
            track_number=2,
            track_total=10,
        )
        audio = AudioInfo(
            codec="mp3",
            sample_rate=44100,
            channels=2,
            bitrate=320000,
            duration=245.365,
        )
        track = Track(
            source_url="https://youtu.be/example",
            output_path=Path("/output/La magia.mp3"),
            metadata=meta,
            audio_info=audio,
        )
        assert track.metadata.album == "Río salvaje"
        assert track.audio_info is not None
        assert track.audio_info.is_valid_mp3
