"""Unit tests for the TransferManager."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yt2ipod.core.models.config import AppConfig, DownloadQuality
from yt2ipod.core.models.device import Device, DeviceCapabilities
from yt2ipod.core.models.transfer import TransferMethod
from yt2ipod.core.transfer.manager import TransferManager


@pytest.fixture
def mock_temp_manager():
    manager = MagicMock()
    manager.create_temp_dir.return_value = Path("/tmp/mock-mnt")
    return manager


@pytest.fixture
def mock_usb_ssh_manager():
    manager = MagicMock()
    # ensure_ssh_over_usb is async
    manager.ensure_ssh_over_usb = AsyncMock(return_value=("127.0.0.1", 2222, MagicMock()))
    manager.stop = AsyncMock()
    return manager


@pytest.mark.asyncio
@patch("yt2ipod.core.transfer.manager.IfuseAFCBackend")
async def test_select_backend_afc(mock_ifuse_cls, mock_temp_manager, mock_usb_ssh_manager):
    # Device has AFC capability
    device = Device(
        model="iPod touch",
        capabilities=DeviceCapabilities(usb=True, afc=True)
    )
    
    config = AppConfig(preferred_transfer_order=[TransferMethod.AFC])
    manager = TransferManager(config=config, temp_manager=mock_temp_manager, usb_ssh_manager=mock_usb_ssh_manager)
    
    # Mock Ifuse mount
    mock_backend = AsyncMock()
    mock_ifuse_cls.return_value = mock_backend
    
    backend, method, ctx = await manager._select_backend(device)
    
    assert backend is mock_backend
    assert method == TransferMethod.AFC
    mock_backend.mount.assert_called_once()


@pytest.mark.asyncio
@patch("yt2ipod.core.transfer.manager.SSHBackend")
async def test_select_backend_usb_ssh(mock_ssh_cls, mock_temp_manager, mock_usb_ssh_manager):
    # Device has USB-SSH capability
    device = Device(
        model="iPod touch",
        capabilities=DeviceCapabilities(usb=True, usb_ssh=True)
    )
    
    config = AppConfig(preferred_transfer_order=[TransferMethod.USB_SSH])
    manager = TransferManager(config=config, temp_manager=mock_temp_manager, usb_ssh_manager=mock_usb_ssh_manager)
    
    mock_backend = MagicMock()
    mock_ssh_cls.return_value = mock_backend
    
    backend, method, ctx = await manager._select_backend(device)
    
    assert backend is mock_backend
    assert method == TransferMethod.USB_SSH
    mock_usb_ssh_manager.ensure_ssh_over_usb.assert_called_once_with(
        udid=device.serial, local_port=2222, device_port=22
    )


@pytest.mark.asyncio
@patch("yt2ipod.core.transfer.manager.IfuseAFCBackend")
async def test_transfer_files_success(mock_ifuse_cls, mock_temp_manager, mock_usb_ssh_manager, tmp_path):
    device = Device(
        model="iPod touch",
        capabilities=DeviceCapabilities(usb=True, afc=True)
    )
    
    config = AppConfig(preferred_transfer_order=[TransferMethod.AFC])
    manager = TransferManager(config=config, temp_manager=mock_temp_manager, usb_ssh_manager=mock_usb_ssh_manager)
    
    # Mock upload
    mock_backend = AsyncMock()
    mock_ifuse_cls.return_value = mock_backend
    
    # Create a temp file to transfer
    f = tmp_path / "song.mp3"
    f.write_text("audio data")
    
    result = await manager.transfer_files([f], device)
    
    assert result.success is True
    assert result.files_transferred == 1
    assert result.bytes_transferred == len("audio data")
    assert result.method == TransferMethod.AFC
    
    # Verify upload was called
    mock_backend.upload.assert_called_once()
    mock_backend.unmount.assert_called_once()
