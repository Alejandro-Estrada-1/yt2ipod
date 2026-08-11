"""Unit tests for the PlainCLIEventHandler."""

from unittest.mock import patch

from yt2ipod.interfaces.plain.handler import PlainCLIEventHandler
from yt2ipod.core.models import events


@patch("builtins.print")
def test_handle_download_started(mock_print):
    handler = PlainCLIEventHandler(use_color=False)
    event = events.DownloadStarted(url="https://youtube.com/watch?v=123", title="My Song")
    
    handler.handle_event(event)
    
    mock_print.assert_any_call("[*] Downloading: https://youtube.com/watch?v=123")
    mock_print.assert_any_call("    Title: My Song")


@patch("builtins.print")
def test_handle_metadata_matched(mock_print):
    handler = PlainCLIEventHandler(use_color=False)
    event = events.MetadataMatched(
        artist="Little Jesus",
        title="TQM",
        album="Río salvaje",
        recording_id="rec-abc",
        confidence=0.9
    )
    
    handler.handle_event(event)
    
    mock_print.assert_any_call("[+] Match found! (Confidence: 90.0%)")
    mock_print.assert_any_call("    Artist: Little Jesus")
    mock_print.assert_any_call("    Title:  TQM")
    mock_print.assert_any_call("    Album:  Río salvaje")
