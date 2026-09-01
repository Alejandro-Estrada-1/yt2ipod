"""Device and DeviceCapabilities domain models.

Generic device abstraction supporting multiple iPod/iPhone models.
The first test device is iPod touch 5G (iOS 9.3.5, 32-bit),
but the architecture supports any legacy Apple device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConnectionType(Enum):
    """How the device is connected."""

    USB = "usb"
    WIFI = "wifi"
    NONE = "none"


class JailbreakStatus(Enum):
    """Jailbreak status of the device."""

    JAILBROKEN = "jailbroken"
    NOT_JAILBROKEN = "not_jailbroken"
    UNKNOWN = "unknown"


class Architecture(Enum):
    """CPU architecture."""

    ARM32 = "32-bit"
    ARM64 = "64-bit"
    UNKNOWN = "unknown"


@dataclass
class DeviceCapabilities:
    """Detected capabilities of a connected device.

    Each capability is independently detected — not all jailbreaks
    provide all capabilities (e.g., AFC2 requires a specific tweak).
    """

    usb: bool = False
    afc: bool = False
    afc2: bool = False
    ssh: bool = False
    usb_ssh: bool = False
    root_filesystem: bool = False
    media_access: bool = False

    @property
    def has_any_transfer_method(self) -> bool:
        """Check if at least one transfer method is available."""
        return self.afc or self.afc2 or self.ssh or self.usb_ssh

    @property
    def available_methods_summary(self) -> list[str]:
        """Human-readable summary of available/unavailable capabilities."""
        checks = [
            ("USB", self.usb),
            ("AFC", self.afc),
            ("AFC2", self.afc2),
            ("SSH", self.ssh),
            ("USB-SSH", self.usb_ssh),
        ]
        return [
            f"{'OK' if available else 'NO'} {name}"
            for name, available in checks
        ]


@dataclass
class Device:
    """A connected Apple device.

    Generic enough to represent iPod touch (all generations),
    legacy iPhones, and potentially future device types.
    """

    model: str = ""  # e.g., "iPod touch 5G"
    model_identifier: str = ""  # e.g., "iPod5,1"
    ios_version: str = ""  # e.g., "9.3.5"
    architecture: Architecture = Architecture.UNKNOWN
    serial: str = ""
    connection: ConnectionType = ConnectionType.NONE
    jailbreak_status: JailbreakStatus = JailbreakStatus.UNKNOWN
    root_access: bool = False
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)

    @property
    def display_name(self) -> str:
        """Human-readable device name."""
        parts = [self.model or "Unknown device"]
        if self.ios_version:
            parts.append(f"iOS {self.ios_version}")
        return " — ".join(parts)

    @property
    def is_connected(self) -> bool:
        """Check if the device has an active connection."""
        return self.connection != ConnectionType.NONE

    def available_transports(self) -> list[str]:
        """Return ordered list of available transport methods.

        Ordered by reliability/speed priority:
        1. AFC (fastest, most reliable for media)
        2. AFC2 (root filesystem access)
        3. USB-SSH (USB tunnel, fast)
        4. Wi-Fi SSH (network, slower)
        """
        transports = []
        if self.capabilities.afc:
            transports.append("afc")
        if self.capabilities.afc2:
            transports.append("afc2")
        if self.capabilities.usb_ssh:
            transports.append("usb_ssh")
        if self.capabilities.ssh:
            transports.append("wifi_ssh")
        return transports

    @property
    def is_jailbroken(self) -> bool:
        """Check if device is known to be jailbroken."""
        return self.jailbreak_status == JailbreakStatus.JAILBROKEN
