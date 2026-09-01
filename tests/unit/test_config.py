"""Tests for AppConfig, SSHSettings, and related enums."""

from pathlib import Path

from yt2ipod.core.models.config import (
    AppConfig,
    DownloadQuality,
    DuplicatePolicy,
    InterfaceMode,
    SSHSettings,
)


class TestInterfaceMode:
    def test_values(self):
        assert InterfaceMode.INTERACTIVE.value == "interactive"
        assert InterfaceMode.PLAIN.value == "plain"
        assert InterfaceMode.JSON.value == "json"


class TestDuplicatePolicy:
    def test_values(self):
        assert DuplicatePolicy.OVERWRITE.value == "overwrite"
        assert DuplicatePolicy.RENAME.value == "rename"
        assert DuplicatePolicy.SKIP.value == "skip"


class TestDownloadQuality:
    def test_ffmpeg_quality_mapping(self):
        assert DownloadQuality.BEST.ffmpeg_quality == 0
        assert DownloadQuality.HIGH.ffmpeg_quality == 2
        assert DownloadQuality.MEDIUM.ffmpeg_quality == 4
        assert DownloadQuality.LOW.ffmpeg_quality == 6

    def test_best_is_default_intent(self):
        """BEST should map to highest quality (lowest number)."""
        assert DownloadQuality.BEST.ffmpeg_quality < DownloadQuality.LOW.ffmpeg_quality


class TestSSHSettings:
    def test_unconfigured(self):
        settings = SSHSettings()
        assert not settings.is_configured
        assert settings.host == ""
        assert settings.port == 22
        assert settings.username == ""
        assert settings.identity_file is None

    def test_configured(self):
        settings = SSHSettings(
            host="192.168.1.100",
            port=22,
            username="mobile",
            identity_file=Path("~/.ssh/id_rsa"),
        )
        assert settings.is_configured
        assert settings.host == "192.168.1.100"
        assert settings.username == "mobile"

    def test_no_password_field(self):
        """SSHSettings must NOT have a password field (security by design)."""
        assert not hasattr(SSHSettings(), "password")


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.output_dir is None
        assert not config.keep_temp
        assert config.download_quality == DownloadQuality.BEST
        assert config.duplicate_policy == DuplicatePolicy.RENAME
        assert config.interface_mode == InterfaceMode.INTERACTIVE
        assert config.genre_fallback == ""

    def test_effective_output_dir_default(self):
        config = AppConfig()
        assert config.effective_output_dir == Path.cwd()

    def test_effective_output_dir_custom(self):
        config = AppConfig(output_dir=Path("/custom/output"))
        assert config.effective_output_dir == Path("/custom/output")

    def test_transfer_priority_default(self):
        config = AppConfig()
        assert config.preferred_transfer_order == ["afc", "afc2", "usb_ssh", "wifi_ssh"]

    def test_custom_transfer_priority(self):
        config = AppConfig(
            preferred_transfer_order=["wifi_ssh", "afc"],
        )
        assert config.preferred_transfer_order == ["wifi_ssh", "afc"]

    def test_ssh_settings_default(self):
        config = AppConfig()
        assert not config.ssh_settings.is_configured

    def test_keep_temp(self):
        config = AppConfig(keep_temp=True)
        assert config.keep_temp
