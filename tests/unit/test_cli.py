"""Unit tests for the CLI entry point."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yt2ipod.cli import main
from yt2ipod.core.models.device import Device, DeviceCapabilities
from yt2ipod.core.transfer.manager import TransferResult


@pytest.fixture
def mock_pipeline():
    with patch("yt2ipod.cli.Pipeline") as mock_cls:
        instance = mock_cls.return_value
        instance.run = AsyncMock()
        yield instance


@pytest.fixture
def mock_detector():
    with patch("yt2ipod.cli.DeviceDetector") as mock_cls:
        instance = mock_cls.return_value
        instance.detect_devices = AsyncMock(return_value=[
            Device(
                model="iPod nano",
                ios_version="1.1",
                capabilities=DeviceCapabilities(usb=True, afc=True)
            )
        ])
        yield instance


@pytest.fixture
def mock_transfer_manager():
    with patch("yt2ipod.cli.TransferManager") as mock_cls:
        instance = mock_cls.return_value
        instance.transfer_files = AsyncMock(return_value=TransferResult(
            success=True,
            files_transferred=1,
            duration=1.0,
            method=MagicMock(value="afc")
        ))
        yield instance


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Download music from YouTube" in captured.out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "yt2ipod" in captured.out


def test_cli_automatic_plain(mock_pipeline):
    # Run main in automatic mode
    exit_code = main(["https://youtube.com/watch?v=123", "--plain"])
    assert exit_code == 0
    mock_pipeline.run.assert_called_once()


def test_cli_automatic_json(mock_pipeline, capsys):
    exit_code = main(["https://youtube.com/watch?v=123", "--json"])
    assert exit_code == 0
    mock_pipeline.run.assert_called_once()


def test_cli_transfer(mock_detector, mock_transfer_manager, tmp_path):
    f = tmp_path / "song.mp3"
    f.write_text("audio")
    
    exit_code = main(["--transfer", str(f)])
    assert exit_code == 0
    mock_transfer_manager.transfer_files.assert_called_once()


def test_cli_import(mock_pipeline, tmp_path):
    f = tmp_path / "song.mp3"
    f.write_text("audio")
    
    exit_code = main(["--import-local", str(f)])
    assert exit_code == 0
    mock_pipeline.run.assert_called_once()
