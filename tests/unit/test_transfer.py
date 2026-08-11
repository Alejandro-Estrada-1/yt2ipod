"""Tests for TransferMethod, TransferResult, and DeviceStorageLayout."""

from yt2ipod.core.models.transfer import (
    DEFAULT_TRANSFER_PRIORITY,
    DeviceStorageLayout,
    TransferMethod,
    TransferResult,
)


class TestTransferMethod:
    """Tests for TransferMethod enum."""

    def test_display_names(self):
        assert TransferMethod.AFC.display_name == "USB / AFC"
        assert TransferMethod.AFC2.display_name == "USB / AFC2"
        assert TransferMethod.USB_SSH.display_name == "USB / SSH"
        assert TransferMethod.WIFI_SSH.display_name == "Wi-Fi / SSH"

    def test_default_priority_order(self):
        assert DEFAULT_TRANSFER_PRIORITY == [
            TransferMethod.AFC,
            TransferMethod.AFC2,
            TransferMethod.USB_SSH,
            TransferMethod.WIFI_SSH,
        ]

    def test_values(self):
        assert TransferMethod.AFC.value == "afc"
        assert TransferMethod.WIFI_SSH.value == "wifi_ssh"


class TestTransferResult:
    """Tests for TransferResult dataclass."""

    def test_successful_transfer(self):
        result = TransferResult(
            method=TransferMethod.AFC,
            success=True,
            files_transferred=2,
            bytes_transferred=10 * 1024 * 1024,
            duration=5.0,
        )
        assert result.success
        assert not result.has_errors
        assert result.files_transferred == 2
        assert result.transfer_speed_mbps == 2.0
        assert "2 file(s)" in result.summary()
        assert "USB / AFC" in result.summary()

    def test_failed_transfer(self):
        result = TransferResult(
            method=TransferMethod.WIFI_SSH,
            success=False,
            errors=["Connection refused"],
        )
        assert not result.success
        assert result.has_errors
        assert "Connection refused" in result.summary()

    def test_zero_duration_speed(self):
        result = TransferResult(duration=0.0)
        assert result.transfer_speed_mbps == 0.0

    def test_defaults(self):
        result = TransferResult()
        assert not result.success
        assert result.files_transferred == 0
        assert result.errors == []


class TestDeviceStorageLayout:
    """Tests for DeviceStorageLayout dataclass."""

    def test_defaults(self):
        layout = DeviceStorageLayout()
        assert layout.media_root == "/var/mobile/Media/"
        assert layout.default_destination == "/var/mobile/Media/Music/"

    def test_custom_paths(self):
        layout = DeviceStorageLayout(
            media_root="/custom/media/",
            music_directory="/custom/media/Music/",
            writable_paths=["/custom/media/", "/custom/other/"],
        )
        assert layout.default_destination == "/custom/media/Music/"
        assert len(layout.writable_paths) == 2
