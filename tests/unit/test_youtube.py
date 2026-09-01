"""Unit tests for the YouTube backend (YtDlpClient).

Uses mocked subprocesses to test parsing and error handling
without requiring an internet connection or the yt-dlp binary.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from yt2ipod.backends.youtube.client import YtDlpClient
from yt2ipod.core.models.errors import DependencyError, DownloadError, ProcessExecutionError
from yt2ipod.core.models.events import DownloadProgress
from yt2ipod.utils.runner import CommandResult


@pytest.fixture
def client():
    return YtDlpClient(binary_path="fake-yt-dlp")


class TestCheckDependency:
    @pytest.mark.asyncio
    @patch("shutil.which", return_value=None)
    async def test_missing_binary(self, mock_which, client):
        with pytest.raises(DependencyError) as exc:
            await client.check_dependency()
        assert "not installed" in str(exc.value)

    @pytest.mark.asyncio
    @patch("shutil.which", return_value="/usr/bin/fake-yt-dlp")
    @patch("yt2ipod.utils.runner.ProcessRunner.run", return_value=CommandResult(0, "yt-dlp 2023.10.13", ""))
    async def test_installed(self, mock_run, mock_which, client):
        # Should not raise
        await client.check_dependency()


class TestGetMetadata:
    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_success(self, mock_run, client):
        fake_json = {
            "title": "La magia",
            "uploader": "Little Jesus",
            "duration": 245.365
        }
        mock_run.return_value = CommandResult(0, json.dumps(fake_json), "")

        track = await client.get_metadata("https://youtu.be/abc")

        assert track.source_url == "https://youtu.be/abc"
        assert track.youtube_title == "La magia"
        assert track.youtube_artist == "Little Jesus"
        assert track.youtube_duration == 245.365

    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_bot_detection_error(self, mock_run, client):
        mock_run.side_effect = ProcessExecutionError(
            "failed",
            exit_code=1,
            stderr="ERROR: Sign in to confirm you're not a bot"
        )

        with pytest.raises(DownloadError) as exc:
            await client.get_metadata("https://youtu.be/abc")

        assert "bot detection" in str(exc.value).lower()

    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run")
    async def test_invalid_json(self, mock_run, client):
        mock_run.return_value = CommandResult(0, "not json", "")

        with pytest.raises(DownloadError) as exc:
            await client.get_metadata("https://youtu.be/abc")

        assert "parse" in str(exc.value)


class TestDownloadAudio:
    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run_stream")
    @patch("pathlib.Path.exists", return_value=True)
    async def test_success_with_progress(self, mock_exists, mock_stream, client):
        # Simulate lines yielded by yt-dlp
        async def fake_stream(*args, **kwargs):
            yield ("stdout", "[download] Destination: /out/La magia [abc].webm")
            yield ("stdout", "[download]   0.0% of    3.45MiB at    1.20MiB/s ETA 00:01")
            yield ("stdout", "[download]  50.0% of    3.45MiB at    1.20MiB/s ETA 00:00")
            yield ("stdout", "[download] 100.0% of    3.45MiB at    1.20MiB/s ETA 00:00")

        mock_stream.side_effect = fake_stream

        events = []
        async for event in client.download_audio("url", Path("/out")):
            events.append(event)

        # 3 progress events + 1 path return
        assert len(events) == 4

        assert isinstance(events[0], DownloadProgress)
        assert events[0].percent == 0.0

        assert isinstance(events[1], DownloadProgress)
        assert events[1].percent == 50.0

        assert isinstance(events[3], Path)
        assert str(events[3]) == "/out/La magia [abc].webm"

    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run_stream")
    @patch("pathlib.Path.exists", return_value=True)
    async def test_already_downloaded(self, mock_exists, mock_stream, client):
        async def fake_stream(*args, **kwargs):
            yield ("stdout", "[download] /out/La magia [abc].webm has already been downloaded")

        mock_stream.side_effect = fake_stream

        events = []
        async for event in client.download_audio("url", Path("/out")):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], Path)
        assert str(events[0]) == "/out/La magia [abc].webm"

    @pytest.mark.asyncio
    @patch("yt2ipod.utils.runner.ProcessRunner.run_stream")
    async def test_no_output_path_found(self, mock_stream, client):
        async def fake_stream(*args, **kwargs):
            yield ("stdout", "some other output")

        mock_stream.side_effect = fake_stream

        with pytest.raises(DownloadError) as exc:
            async for _ in client.download_audio("url", Path("/out")):
                pass

        assert "output file path could not be determined" in str(exc.value)
