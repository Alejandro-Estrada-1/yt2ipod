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


def test_tui_app_menu_selection(mock_detector):
    app = YT2iPodApp(detector=mock_detector)
    
    # Mock event and selected list item
    mock_item = MagicMock()
    mock_static = MagicMock()
    mock_static.renderable = "Settings"
    mock_item.children = [mock_static]
    
    # We mock ListView
    mock_list_view = MagicMock()
    mock_list_view.index_of.return_value = 4  # corresponds to "Settings" in MAIN_MENU
    app.menu_list = mock_list_view
    
    mock_event = MagicMock()
    mock_event.item = mock_item
    
    with patch.object(app, "push_screen") as mock_push:
        app.on_list_view_selected(mock_event)
        
    assert "Settings" in app.nav_stack
    mock_push.assert_called_once()
