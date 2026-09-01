"""Unit tests for the system file dialog utility."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from yt2ipod.utils.dialogs import is_gui_dialog_available, pick_directory_dialog, pick_files_dialog


def test_is_gui_dialog_available():
    with patch("os.environ.get", return_value=":0"), patch("shutil.which", return_value="/usr/bin/zenity"):
        assert is_gui_dialog_available() is True

    with patch("os.environ.get", return_value=None), patch("shutil.which", return_value="/usr/bin/zenity"):
        assert is_gui_dialog_available() is False

    with patch("os.environ.get", return_value=":0"), patch("shutil.which", return_value=None):
        assert is_gui_dialog_available() is False


def test_pick_files_dialog(tmp_path):
    f1 = tmp_path / "song1.mp3"
    f2 = tmp_path / "song2.mp3"
    f1.touch()
    f2.touch()

    # Success case with multiple files
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = f"{f1}|{f2}\n"

    with patch("yt2ipod.utils.dialogs.is_gui_dialog_available", return_value=True), patch(
        "subprocess.run", return_value=mock_res
    ):
        files = pick_files_dialog(title="Test", multiple=True)
        assert len(files) == 2
        assert f1 in files
        assert f2 in files

    # Cancel case
    mock_cancel = MagicMock()
    mock_cancel.returncode = 1
    mock_cancel.stdout = ""

    with patch("yt2ipod.utils.dialogs.is_gui_dialog_available", return_value=True), patch(
        "subprocess.run", return_value=mock_cancel
    ):
        files = pick_files_dialog(title="Test", multiple=True)
        assert files == []


def test_pick_directory_dialog(tmp_path):
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = f"{tmp_path}\n"

    with patch("yt2ipod.utils.dialogs.is_gui_dialog_available", return_value=True), patch(
        "subprocess.run", return_value=mock_res
    ):
        chosen_dir = pick_directory_dialog(title="Test Dir")
        assert chosen_dir == tmp_path

    # Cancel case
    mock_cancel = MagicMock()
    mock_cancel.returncode = 1
    mock_cancel.stdout = ""

    with patch("yt2ipod.utils.dialogs.is_gui_dialog_available", return_value=True), patch(
        "subprocess.run", return_value=mock_cancel
    ):
        chosen_dir = pick_directory_dialog(title="Test Dir")
        assert chosen_dir is None
