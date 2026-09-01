"""Unit tests for the new operational Textual TUI screens."""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import pytest

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.config import AppConfig
from yt2ipod.interfaces.textual.screens import (
    AboutScreen,
    DeviceInfoScreen,
    DownloadScreen,
    ImportScreen,
    SelectFilesScreen,
    SettingsScreen,
)


def test_about_screen():
    screen = AboutScreen()
    assert screen is not None


def test_settings_screen():
    config = AppConfig()
    screen = SettingsScreen(config=config)
    assert screen.config is config


@pytest.mark.asyncio
async def test_device_info_screen():
    detector = MagicMock(spec=DeviceDetector)
    detector.detect_devices = AsyncMock(return_value=[])
    
    screen = DeviceInfoScreen(detector=detector)
    assert screen.detector is detector
    
    # Check that refresh_devices executes and queries detector
    with patch.object(screen, "query_one") as mock_query:
        # Mock status label and table
        mock_status = MagicMock()
        mock_table = MagicMock()
        mock_query.side_effect = lambda selector, *args: mock_status if "status" in selector else mock_table
        
        await screen.refresh_devices()
        
    detector.detect_devices.assert_called_once()


def test_download_screen():
    config = AppConfig()
    screen = DownloadScreen(config=config)
    assert screen.config is config
    assert screen.pipeline is not None


def test_import_screen():
    config = AppConfig()
    screen = ImportScreen(config=config)
    assert screen.config is config
    assert screen.pipeline is not None


def test_select_files_screen():
    config = AppConfig()
    screen = SelectFilesScreen(config=config)
    assert screen.config is config
    assert screen.transfer_manager is not None
