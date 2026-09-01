"""Unit tests for the FileSystemBackends."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt2ipod.core.filesystem.backend import LocalBackend, IfuseAFCBackend, SSHBackend
from yt2ipod.core.models.errors import FileSystemError
from yt2ipod.utils.runner import CommandResult


@pytest.mark.asyncio
async def test_local_backend(tmp_path):
    base = tmp_path / "device"
    backend = LocalBackend(base)

    # test upload
    f = tmp_path / "one.mp3"
    f.write_text("audio data")
    
    await backend.upload([f], Path("Music"))
    assert (base / "Music" / "one.mp3").exists()
    assert (base / "Music" / "one.mp3").read_text() == "audio data"

    # test list
    lst = await backend.list(Path("Music"))
    assert any(p.name == "one.mp3" for p in lst)

    # test exists
    assert await backend.exists(Path("Music/one.mp3")) is True
    assert await backend.exists(Path("Music/two.mp3")) is False

    # test download
    local_dest = tmp_path / "dl.mp3"
    await backend.download(Path("Music/one.mp3"), local_dest)
    assert local_dest.exists()
    assert local_dest.read_text() == "audio data"

    # test delete
    await backend.delete(Path("Music/one.mp3"))
    assert not (base / "Music" / "one.mp3").exists()
    assert await backend.exists(Path("Music/one.mp3")) is False


@pytest.mark.asyncio
@patch("shutil.which")
@patch("yt2ipod.utils.runner.ProcessRunner.run")
async def test_ifuse_backend_mount_and_operations(mock_run, mock_which, tmp_path):
    mock_which.side_effect = lambda name: "/usr/bin/ifuse" if name in ("ifuse", "fusermount") else None
    mock_run.return_value = CommandResult(0, "", "")

    mount_point = tmp_path / "mnt"
    backend = IfuseAFCBackend(mount_point=mount_point, udid="udid-12345")

    # Mount should trigger ifuse command
    await backend.mount()
    assert mount_point.exists()

    mock_run.assert_called_with(["ifuse", "-u", "udid-12345", str(mount_point)], check=True)

    # Simulate directory structure
    music_dir = mount_point / "Music"
    music_dir.mkdir(parents=True)
    (music_dir / "track.mp3").write_text("mp3 binary")

    lst = await backend.list(Path("Music"))
    assert any(p.name == "track.mp3" for p in lst)

    # Unmount should trigger fusermount -u
    mock_run.reset_mock()
    await backend.unmount()
    mock_run.assert_called_with(["fusermount", "-u", str(mount_point)], check=True)


@pytest.mark.asyncio
@patch("shutil.which")
@patch("yt2ipod.utils.runner.ProcessRunner.run")
async def test_ssh_backend(mock_run, mock_which, tmp_path):
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"
    mock_run.return_value = CommandResult(0, "", "")

    backend = SSHBackend(host="192.168.1.100", port=22, username="mobile")

    # Test mkdir
    await backend.mkdir(Path("/var/mobile/Media/Music"))
    mock_run.assert_any_call([
        "ssh", "-p", "22", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
        "mobile@192.168.1.100", "mkdir -p '/var/mobile/Media/Music'"
    ], check=True)

    # Test upload
    local_file = tmp_path / "track.mp3"
    local_file.write_text("mp3 file")
    
    await backend.upload([local_file], Path("/var/mobile/Media/Music"))
    # SCP command must be called
    scp_call = mock_run.call_args[0][0]
    assert scp_call[0] == "scp"
    assert scp_call[1] == "-P"
    assert scp_call[2] == "22"
    assert str(local_file) in scp_call
    assert "mobile@192.168.1.100:'/var/mobile/Media/Music'" in scp_call
