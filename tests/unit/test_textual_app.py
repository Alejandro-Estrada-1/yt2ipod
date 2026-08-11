"""Unit tests for the Textual TUI app."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.device import Device, DeviceCapabilities
from yt2ipod.interfaces.textual.app import YT2iPodApp


@pytest.fixture
def mock_detector():
    detector = MagicMock(spec=DeviceDetector)
    detector.detect_devices = AsyncMock(return_value=[
        Device(
            model="iPod nano",
            model_identifier="iPod3,1",
            ios_version="1.1.3",
            serial="SN112233",
            capabilities=DeviceCapabilities(usb=True, afc=True)
        )
    ])
    return detector


def test_tui_app_instantiation(mock_detector):
    app = YT2iPodApp(detector=mock_detector)
    assert app.detector is mock_detector
    assert app.nav_stack == ["main"]


@pytest.mark.asyncio
async def test_tui_app_refresh_devices(mock_detector):
    app = YT2iPodApp(detector=mock_detector)
    
    # We mock the query_one method to return a dummy DeviceStatus widget
    mock_status_widget = MagicMock()
    
    with patch.object(app, "query_one", return_value=mock_status_widget):
        await app.action_refresh_devices()
        
    mock_detector.detect_devices.assert_called_once()
    assert mock_status_widget.update_status.call_count == 2
    
    # Verify what was printed/updated
    called_lines = mock_status_widget.update_status.call_args_list[-1][0][0]
    assert any("iPod nano" in line for line in called_lines)
