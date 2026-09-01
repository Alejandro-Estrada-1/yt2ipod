"""Tests for platform detection.

Uses mocking to test Termux and macOS detection without
requiring those actual environments.
"""

import os
from unittest.mock import patch

from yt2ipod.platform.detection import (
    PlatformType,
    detect_platform,
    get_temp_directory,
)


class TestPlatformType:
    def test_display_names(self):
        assert PlatformType.MACOS.display_name == "macOS"
        assert PlatformType.LINUX.display_name == "Linux"
        assert PlatformType.TERMUX.display_name == "Termux"
        assert PlatformType.UNKNOWN.display_name == "Unknown"

    def test_values(self):
        assert PlatformType.MACOS.value == "macos"
        assert PlatformType.LINUX.value == "linux"
        assert PlatformType.TERMUX.value == "termux"


class TestDetectPlatform:
    @patch.dict(os.environ, {"TERMUX_VERSION": "0.118.0"}, clear=False)
    @patch("sys.platform", "linux")
    def test_detect_termux(self):
        """Termux should be detected even though sys.platform is 'linux'."""
        result = detect_platform()
        assert result == PlatformType.TERMUX

    @patch.dict(os.environ, {}, clear=False)
    @patch("sys.platform", "darwin")
    @patch("yt2ipod.platform.detection._is_termux", return_value=False)
    def test_detect_macos(self, _mock_termux):
        result = detect_platform()
        assert result == PlatformType.MACOS

    @patch.dict(os.environ, {}, clear=False)
    @patch("sys.platform", "linux")
    @patch("yt2ipod.platform.detection._is_termux", return_value=False)
    def test_detect_linux(self, _mock_termux):
        result = detect_platform()
        assert result == PlatformType.LINUX

    @patch.dict(os.environ, {}, clear=False)
    @patch("sys.platform", "win32")
    @patch("yt2ipod.platform.detection._is_termux", return_value=False)
    def test_detect_unknown(self, _mock_termux):
        result = detect_platform()
        assert result == PlatformType.UNKNOWN

    @patch.dict(os.environ, {"TERMUX_VERSION": "0.118.0"}, clear=False)
    @patch("sys.platform", "linux")
    def test_termux_takes_precedence_over_linux(self):
        """Termux check must happen BEFORE generic Linux check."""
        result = detect_platform()
        assert result == PlatformType.TERMUX


class TestGetTempDirectory:
    @patch("yt2ipod.platform.detection.detect_platform", return_value=PlatformType.LINUX)
    def test_linux_temp(self, _mock):
        temp = get_temp_directory()
        assert temp.is_absolute()

    @patch("yt2ipod.platform.detection.detect_platform", return_value=PlatformType.MACOS)
    def test_macos_temp(self, _mock):
        temp = get_temp_directory()
        assert temp.is_absolute()

    def test_temp_is_path(self):
        """Temp directory should always return a Path object."""
        from pathlib import Path
        temp = get_temp_directory()
        assert isinstance(temp, Path)
