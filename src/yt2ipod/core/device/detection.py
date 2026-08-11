"""Device detection utility (Phase 9).

Detects connected iOS devices and queries their capabilities using libimobiledevice,
ifuse, usbmuxd, and ssh binaries.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from yt2ipod.core.models.device import (
    Architecture,
    ConnectionType,
    Device,
    DeviceCapabilities,
    JailbreakStatus,
)
from yt2ipod.utils.logging import get_logger
from yt2ipod.utils.runner import ProcessRunner

logger = get_logger(__name__)


class DeviceDetector:
    """Detects connected iOS/iPod devices and queries their capability set."""

    def __init__(
        self,
        idevice_id_path: str = "idevice_id",
        ideviceinfo_path: str = "ideviceinfo",
    ) -> None:
        self.idevice_id = idevice_id_path
        self.ideviceinfo = ideviceinfo_path

    def _has_binary(self, name: str) -> bool:
        return shutil.which(name) is not None

    async def list_udids(self) -> list[str]:
        """List UDIDs of connected devices via USB."""
        if not self._has_binary(self.idevice_id):
            logger.debug("idevice_id binary not found.")
            return []

        try:
            result = await ProcessRunner.run([self.idevice_id, "-l"], timeout=5.0)
            if not result.success:
                return []
            stdout = result.stdout.strip()
            return [line.strip() for line in stdout.splitlines() if line.strip()]
        except Exception as e:
            logger.error(f"Error listing device UDIDs: {e}")
            return []

    async def query_device_value(self, udid: str, key: str) -> str:
        """Query a single configuration value from the device using ideviceinfo."""
        if not self._has_binary(self.ideviceinfo):
            return ""

        cmd = [self.ideviceinfo, "-u", udid, "-k", key]
        try:
            result = await ProcessRunner.run(cmd, timeout=5.0)
            if result.success:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Failed to query {key} for device {udid}: {e}")
        return ""

    async def detect_devices(self) -> list[Device]:
        """Perform full detection of connected devices.

        Returns:
            List of detected Device objects with capabilities mapped.
        """
        udids = await self.list_udids()
        devices: list[Device] = []

        # Check helper binaries
        has_ifuse = self._has_binary("ifuse")
        has_iproxy = self._has_binary("iproxy")
        has_ssh = self._has_binary("ssh")
        has_usbmuxd = self._has_binary("usbmuxd") or (
            self._has_binary("pgrep")
            and (await ProcessRunner.run(["pgrep", "-f", "usbmuxd"])).success
        )

        for udid in udids:
            # Query info
            model = await self.query_device_value(udid, "ProductType")
            # Map common internal model identifiers to human-readable names if needed,
            # but we can also query DeviceName
            device_name = await self.query_device_value(udid, "DeviceName")
            ios_version = await self.query_device_value(udid, "ProductVersion")
            serial = await self.query_device_value(udid, "SerialNumber")
            wifi_address = await self.query_device_value(udid, "WiFiAddress")
            cpu_arch = await self.query_device_value(udid, "CPUArchitecture")

            # Resolve architecture enum
            arch = Architecture.ARM32
            if cpu_arch and "64" in cpu_arch:
                arch = Architecture.ARM64

            # Capabilities heuristics
            caps = DeviceCapabilities(
                usb=True,
                afc=has_ifuse,
                afc2=False,  # Can only be verified on mount try, default False
                ssh=bool(wifi_address) and has_ssh,
                usb_ssh=has_iproxy and has_ssh,
                root_filesystem=False, # Standard is media-only
                media_access=has_ifuse,
            )

            # Build rich Device model
            device = Device(
                model=device_name or model or "iOS Device",
                model_identifier=model or "Unknown",
                ios_version=ios_version or "Unknown",
                architecture=arch,
                serial=udid,
                connection=ConnectionType.USB,
                jailbreak_status=JailbreakStatus.UNKNOWN, # Default unless we check afc2/ssh
                root_access=False,
                capabilities=caps,
            )
            # Store UDID as serial or custom attribute if needed
            # Device model has a 'serial' field which is perfect
            devices.append(device)

        return devices
