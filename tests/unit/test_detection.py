"""Unit tests for the DeviceDetector."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.utils.runner import CommandResult


@pytest.mark.asyncio
@patch("shutil.which")
async def test_no_idevice_tools(mock_which):
    mock_which.return_value = None
    detector = DeviceDetector()
    
    udids = await detector.list_udids()
    assert udids == []
    
    devices = await detector.detect_devices()
    assert devices == []


@pytest.mark.asyncio
@patch("shutil.which")
@patch("yt2ipod.utils.runner.ProcessRunner.run")
async def test_detect_one_device_with_tools(mock_run, mock_which):
    # Mock which to report all binaries are found
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    # Mock outputs for idevice_id and ideviceinfo
    def mock_run_cmd(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "idevice_id -l" in cmd_str:
            return CommandResult(0, "abcd-udid\n", "")
        elif "ProductType" in cmd_str:
            return CommandResult(0, "iPod5,1\n", "")
        elif "DeviceName" in cmd_str:
            return CommandResult(0, "Ale's iPod\n", "")
        elif "ProductVersion" in cmd_str:
            return CommandResult(0, "9.3.5\n", "")
        elif "SerialNumber" in cmd_str:
            return CommandResult(0, "SN123456\n", "")
        elif "WiFiAddress" in cmd_str:
            return CommandResult(0, "192.168.1.100\n", "")
        elif "CPUArchitecture" in cmd_str:
            return CommandResult(0, "armv7s\n", "")
        return CommandResult(0, "", "")

    mock_run.side_effect = mock_run_cmd

    detector = DeviceDetector()
    udids = await detector.list_udids()
    assert udids == ["abcd-udid"]

    devices = await detector.detect_devices()
    assert len(devices) == 1
    d = devices[0]
    
    assert d.model == "Ale's iPod"
    assert d.model_identifier == "iPod5,1"
    assert d.ios_version == "9.3.5"
    assert d.serial == "SN123456"
    assert d.is_connected is True
    assert d.capabilities.usb is True
    assert d.capabilities.afc is True
    assert d.capabilities.usb_ssh is True
    assert d.capabilities.ssh is True
