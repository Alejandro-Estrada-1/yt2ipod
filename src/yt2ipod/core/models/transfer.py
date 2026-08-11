"""Transfer-related domain models.

TransferMethod, TransferResult, and DeviceStorageLayout define
the contract between the transfer manager and its backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TransferMethod(Enum):
    """Available transfer methods, ordered by default priority."""

    AFC = "afc"
    AFC2 = "afc2"
    USB_SSH = "usb_ssh"
    WIFI_SSH = "wifi_ssh"

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        names = {
            TransferMethod.AFC: "USB / AFC",
            TransferMethod.AFC2: "USB / AFC2",
            TransferMethod.USB_SSH: "USB / SSH",
            TransferMethod.WIFI_SSH: "Wi-Fi / SSH",
        }
        return names[self]


# Default priority order for automatic transport selection
DEFAULT_TRANSFER_PRIORITY: list[TransferMethod] = [
    TransferMethod.AFC,
    TransferMethod.AFC2,
    TransferMethod.USB_SSH,
    TransferMethod.WIFI_SSH,
]


@dataclass
class TransferResult:
    """Result of a file transfer operation."""

    method: TransferMethod = TransferMethod.AFC
    success: bool = False
    files_transferred: int = 0
    bytes_transferred: int = 0
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0  # seconds

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during transfer."""
        return len(self.errors) > 0

    @property
    def transfer_speed_mbps(self) -> float:
        """Calculate transfer speed in MB/s."""
        if self.duration <= 0:
            return 0.0
        return (self.bytes_transferred / (1024 * 1024)) / self.duration

    def summary(self) -> str:
        """Human-readable transfer summary."""
        if self.success:
            return (
                f"Transferred {self.files_transferred} file(s) "
                f"via {self.method.display_name} "
                f"in {self.duration:.1f}s"
            )
        error_msg = "; ".join(self.errors) if self.errors else "unknown error"
        return f"Transfer failed: {error_msg}"


@dataclass
class DeviceStorageLayout:
    """Storage paths on the target device.

    Not hardcoded — can be configured per device or detected automatically.
    """

    media_root: str = "/var/mobile/Media/"
    music_directory: str = "/var/mobile/Media/Music/"
    writable_paths: list[str] = field(default_factory=list)

    @property
    def default_destination(self) -> str:
        """Default path where music files should be placed."""
        return self.music_directory
