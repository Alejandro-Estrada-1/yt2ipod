"""Unit tests for the USBSSHManager."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from yt2ipod.core.device.usb_ssh import USBSSHManager
from yt2ipod.core.models.errors import ProcessExecutionError


class DummyPopen:
    def __init__(self):
        self._poll_count = 0

    def terminate(self):
        pass

    def kill(self):
        pass

    def poll(self):
        self._poll_count += 1
        if self._poll_count > 2:
            return 0
        return None


@pytest.mark.asyncio
@patch("shutil.which")
async def test_iproxy_not_available(mock_which):
    mock_which.return_value = None
    manager = USBSSHManager()

    # ensure_ssh_over_usb should raise ProcessExecutionError because iproxy not found
    with pytest.raises(ProcessExecutionError) as exc:
        await manager.ensure_ssh_over_usb(udid=None, local_port=2222)

    assert "iproxy is not installed" in str(exc.value)


@pytest.mark.asyncio
@patch("shutil.which")
@patch("subprocess.Popen")
async def test_start_iproxy_and_stop(mock_popen, mock_which):
    mock_which.return_value = "/usr/bin/iproxy"
    dummy_proc = DummyPopen()
    mock_popen.return_value = dummy_proc

    manager = USBSSHManager()

    # Mock is_port_open to return True after 3 calls
    calls = []
    async def mock_is_port_open(self, host, port, timeout=0.5):
        calls.append(True)
        return len(calls) > 3

    with patch.object(USBSSHManager, "is_port_open", mock_is_port_open):
        host, port, proc = await manager.ensure_ssh_over_usb(udid="udid-1", local_port=2222)
        assert host == "127.0.0.1"
        assert port == 2222
        assert proc is dummy_proc

    # Verify Popen arguments
    mock_popen.assert_called_with(
        ["iproxy", "2222", "22", "-u", "udid-1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Test stop
    await manager.stop()
    assert manager._proc is None


@pytest.mark.asyncio
@patch("shutil.which")
async def test_ensure_ssh_over_usb_port_already_open(mock_which):
    mock_which.return_value = "/usr/bin/iproxy"
    manager = USBSSHManager()

    async def mock_is_port_open(self, host, port, timeout=0.5):
        return True

    with patch.object(USBSSHManager, "is_port_open", mock_is_port_open):
        host, port, proc = await manager.ensure_ssh_over_usb(udid=None, local_port=2222)
        assert host == "127.0.0.1"
        assert port == 2222
        assert proc is None
