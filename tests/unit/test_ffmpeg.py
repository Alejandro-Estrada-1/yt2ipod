"""Unit tests for the FFmpeg backend."""

from pathlib import Path
from unittest.mock import patch

import pytest

from yt2ipod.backends.ffmpeg.client import FFmpegClient
from yt2ipod.core.models.errors import ConversionError, DependencyError, ProcessExecutionError
from yt2ipod.core.models.track import TrackMetadata
from yt2ipod.utils.runner import CommandResult


@pytest.fixture
def client():
    return FFmpegClient(ffmpeg_path="fake-ffmpeg", ffprobe_path="fake-ffprobe")


class TestCheckDependency:
    @pytest.mark.asyncio
    @patch("shutil.which")
    async def test_missing_binary(self, mock_which, client):
        mock_which.side_effect = lambda x: None

        with pytest.raises(DependencyError) as exc:
            await client.check_dependency()

        assert "not installed" in str(exc.value)

    @pytest.mark.asyncio
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_installed(self, mock_run, mock_which, client):
        mock_run.return_value = CommandResult(0, "version", "")
        # Should not raise
        await client.check_dependency()


class TestGetDuration:
    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_success(self, mock_run, client):
        mock_run.return_value = CommandResult(0, "245.365\n", "")

        duration = await client.get_duration(Path("audio.mp3"))
        assert duration == 245.365

        # Verify ffprobe was called with correct arguments
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "fake-ffprobe"
        assert "-show_entries" in cmd
        assert "format=duration" in cmd

    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_failure(self, mock_run, client):
        mock_run.side_effect = ProcessExecutionError("failed", 1, stderr="Invalid data found")

        with pytest.raises(ConversionError) as exc:
            await client.get_duration(Path("audio.mp3"))

        assert "Failed to get duration" in str(exc.value)


class TestConvertToMp3:
    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run_stream")
    async def test_progress_parsing(self, mock_stream, client):
        # 100 seconds total
        async def fake_stream(*args, **kwargs):
            yield ("stderr", "size=  128kB time=00:00:25.00 bitrate= 320.0kbits/s")
            yield ("stderr", "size=  256kB time=00:00:50.00 bitrate= 320.0kbits/s")
            yield ("stderr", "size=  512kB time=00:01:15.00 bitrate= 320.0kbits/s")

        mock_stream.side_effect = fake_stream

        events = []
        async for event in client.convert_to_mp3(Path("in.webm"), Path("out.mp3"), total_duration=100.0):
            events.append(event)

        assert len(events) == 4  # 3 parsed + 1 final 100%

        assert events[0].percent == 25.0
        assert events[1].percent == 50.0
        assert events[2].percent == 75.0
        assert events[3].percent == 100.0

    @pytest.mark.asyncio
    @patch("yt2ipod.backends.ffmpeg.client.FFmpegClient.get_duration", return_value=100.0)
    @patch("yt2ipod.utils.runner.ProcessRunner.run_stream")
    async def test_auto_duration(self, mock_stream, mock_get_duration, client):
        async def fake_stream(*args, **kwargs):
            yield ("stderr", "time=00:00:10.00")

        mock_stream.side_effect = fake_stream

        events = []
        async for event in client.convert_to_mp3(Path("in.webm"), Path("out.mp3")):
            events.append(event)

        assert events[0].percent == 10.0
        mock_get_duration.assert_called_once_with(Path("in.webm"))


class TestEmbedMetadata:
    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_without_artwork(self, mock_run, client):
        metadata = TrackMetadata(
            title="TQM",
            artist="Little Jesus",
            album="Rio Salvaje",
            album_artist="Little Jesus",
            track_number=2,
            track_total=10,
            date="2016",
            genre="Indie Rock"
        )

        await client.embed_metadata(Path("in.mp3"), Path("out.mp3"), metadata)

        cmd = mock_run.call_args[0][0]
        assert "-metadata" in cmd
        assert "title=TQM" in cmd
        assert "artist=Little Jesus" in cmd
        assert "album=Rio Salvaje" in cmd
        assert "album_artist=Little Jesus" in cmd
        assert "date=2016" in cmd
        assert "genre=Indie Rock" in cmd
        assert "track=2/10" in cmd
        assert "-c" in cmd
        assert "copy" in cmd

    @pytest.mark.asyncio
    @patch("pathlib.Path.exists", return_value=True)
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_with_artwork(self, mock_run, mock_exists, client):
        metadata = TrackMetadata(title="Test")
        artwork_path = Path("cover.jpg")

        await client.embed_metadata(Path("in.mp3"), Path("out.mp3"), metadata, artwork_path)

        cmd = mock_run.call_args[0][0]
        assert "-i" in cmd
        assert "cover.jpg" in cmd
        assert "-map" in cmd
        assert "0:0" in cmd
        assert "1:0" in cmd
        assert "-c:v" in cmd
        assert "mjpeg" in cmd
        assert "-disposition:v" in cmd
        assert "attached_pic" in cmd
