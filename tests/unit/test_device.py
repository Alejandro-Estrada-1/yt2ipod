"""Tests for Device and DeviceCapabilities models."""

from yt2ipod.core.models.device import (
    Architecture,
    ConnectionType,
    Device,
    DeviceCapabilities,
    JailbreakStatus,
)


class TestDeviceCapabilities:
    """Tests for DeviceCapabilities dataclass."""

    def test_full_capabilities(self):
        caps = DeviceCapabilities(
            usb=True,
            afc=True,
            afc2=True,
            ssh=True,
            usb_ssh=True,
            root_filesystem=True,
            media_access=True,
        )
        assert caps.has_any_transfer_method
        summary = caps.available_methods_summary
        assert "OK USB" in summary
        assert "OK AFC" in summary
        assert "OK AFC2" in summary
        assert "OK SSH" in summary
        assert "OK USB-SSH" in summary

    def test_no_capabilities(self):
        caps = DeviceCapabilities()
        assert not caps.has_any_transfer_method
        summary = caps.available_methods_summary
        assert "NO USB" in summary
        assert "NO AFC" in summary

    def test_afc_only(self):
        caps = DeviceCapabilities(usb=True, afc=True, media_access=True)
        assert caps.has_any_transfer_method
        assert caps.afc
        assert not caps.afc2
        assert not caps.ssh

    def test_ssh_without_afc2(self):
        """Not all jailbreaks provide AFC2."""
        caps = DeviceCapabilities(usb=True, afc=True, ssh=True)
        assert caps.has_any_transfer_method
        assert not caps.afc2

    def test_mixed_availability_summary(self):
        caps = DeviceCapabilities(usb=True, afc=True, afc2=False, ssh=True, usb_ssh=False)
        summary = caps.available_methods_summary
        assert "OK USB" in summary
        assert "OK AFC" in summary
        assert "NO AFC2" in summary
        assert "OK SSH" in summary
        assert "NO USB-SSH" in summary


class TestDevice:
    """Tests for Device dataclass."""

    def test_ipod_touch_5g(self):
        """First test device: iPod touch 5G."""
        device = Device(
            model="iPod touch 5G",
            model_identifier="iPod5,1",
            ios_version="9.3.5",
            architecture=Architecture.ARM32,
            serial="ABCDEF123456",
            connection=ConnectionType.USB,
            jailbreak_status=JailbreakStatus.JAILBROKEN,
            root_access=True,
            capabilities=DeviceCapabilities(
                usb=True,
                afc=True,
                afc2=False,
                ssh=True,
                usb_ssh=True,
                root_filesystem=True,
                media_access=True,
            ),
        )
        assert device.display_name == "iPod touch 5G — iOS 9.3.5"
        assert device.is_connected
        assert device.is_jailbroken
        assert device.architecture == Architecture.ARM32

    def test_available_transports_priority(self):
        """Transports must be ordered: AFC > AFC2 > USB-SSH > Wi-Fi SSH."""
        device = Device(
            capabilities=DeviceCapabilities(
                afc=True,
                afc2=True,
                ssh=True,
                usb_ssh=True,
            ),
        )
        transports = device.available_transports()
        assert transports == ["afc", "afc2", "usb_ssh", "wifi_ssh"]

    def test_available_transports_afc_only(self):
        device = Device(
            capabilities=DeviceCapabilities(afc=True),
        )
        transports = device.available_transports()
        assert transports == ["afc"]

    def test_available_transports_ssh_only(self):
        device = Device(
            capabilities=DeviceCapabilities(ssh=True),
        )
        transports = device.available_transports()
        assert transports == ["wifi_ssh"]

    def test_available_transports_none(self):
        device = Device()
        assert device.available_transports() == []

    def test_not_connected(self):
        device = Device()
        assert not device.is_connected
        assert device.connection == ConnectionType.NONE

    def test_unknown_jailbreak(self):
        device = Device()
        assert not device.is_jailbroken
        assert device.jailbreak_status == JailbreakStatus.UNKNOWN

    def test_display_name_no_ios(self):
        device = Device(model="iPod touch 5G")
        assert device.display_name == "iPod touch 5G"

    def test_display_name_unknown(self):
        device = Device()
        assert device.display_name == "Unknown device"

    def test_architecture_enum_values(self):
        assert Architecture.ARM32.value == "32-bit"
        assert Architecture.ARM64.value == "64-bit"
