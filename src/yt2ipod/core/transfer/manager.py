"""Transfer manager for orchestrating device file transfers (Phase 11).

Selects the best available transfer method based on device capabilities and
executes the copy operation using the corresponding FileSystemBackend.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

from yt2ipod.core.device.usb_ssh import USBSSHManager
from yt2ipod.core.filesystem.backend import FileSystemBackend, IfuseAFCBackend, LocalBackend, SSHBackend
from yt2ipod.core.models.config import AppConfig
from yt2ipod.core.models.device import Device
from yt2ipod.core.models.transfer import TransferMethod, TransferResult, DeviceStorageLayout
from yt2ipod.core.cleanup.manager import TemporaryFileManager
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)


class TransferManager:
    """Orchestrates transferring files to connected devices.

    Determines the best available transfer method based on device capabilities,
    sets up the connection/mounts, and copies the files.
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        temp_manager: TemporaryFileManager | None = None,
        usb_ssh_manager: USBSSHManager | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.temp_manager = temp_manager or TemporaryFileManager()
        self.usb_ssh_manager = usb_ssh_manager or USBSSHManager()

    async def _select_backend(
        self, device: Device
    ) -> tuple[FileSystemBackend | None, TransferMethod | None, any]:
        """Iterate through preferred transfer order and return the first matching backend.

        Returns:
            Tuple of (FileSystemBackend, TransferMethod, context_object) or (None, None, None).
            The context_object can be used for cleanup (e.g. terminating iproxy process).
        """
        priority = self.config.preferred_transfer_order or [
            m.value for m in self.config.preferred_transfer_order
        ]

        # Ensure we have strings for comparison
        order = []
        for method in priority:
            if isinstance(method, TransferMethod):
                order.append(method.value)
            else:
                order.append(str(method))

        caps = device.capabilities

        for m_str in order:
            if m_str == "afc" and caps.afc and caps.usb:
                # Mount point in temporary directory
                try:
                    mount_dir = self.temp_manager.create_temp_dir(prefix="mnt-afc-")
                    backend = IfuseAFCBackend(mount_point=mount_dir, udid=device.serial)
                    await backend.mount()
                    return backend, TransferMethod.AFC, None
                except Exception as e:
                    logger.debug(f"Failed to initialize IfuseAFCBackend for AFC: {e}")
                    continue

            elif m_str == "afc2" and caps.afc2 and caps.usb:
                try:
                    mount_dir = self.temp_manager.create_temp_dir(prefix="mnt-afc2-")
                    backend = IfuseAFCBackend(mount_point=mount_dir, udid=device.serial)
                    await backend.mount()
                    return backend, TransferMethod.AFC2, None
                except Exception as e:
                    logger.debug(f"Failed to initialize IfuseAFCBackend for AFC2: {e}")
                    continue

            elif m_str == "usb_ssh" and caps.usb_ssh and caps.usb:
                try:
                    host, port, proc = await self.usb_ssh_manager.ensure_ssh_over_usb(
                        udid=device.serial,
                        local_port=2222,
                        device_port=22
                    )
                    backend = SSHBackend(
                        host=host,
                        port=port,
                        username=self.config.ssh_settings.username or "mobile",
                        identity_file=self.config.ssh_settings.identity_file
                    )
                    return backend, TransferMethod.USB_SSH, proc
                except Exception as e:
                    logger.debug(f"Failed to establish SSH over USB tunnel: {e}")
                    continue

            elif m_str == "wifi_ssh" and caps.ssh:
                # Read hostname/IP from SSH settings or fallback to device properties
                host = self.config.ssh_settings.host or device.serial
                if not host:
                    continue
                try:
                    backend = SSHBackend(
                        host=host,
                        port=self.config.ssh_settings.port,
                        username=self.config.ssh_settings.username or "mobile",
                        identity_file=self.config.ssh_settings.identity_file
                    )
                    return backend, TransferMethod.WIFI_SSH, None
                except Exception as e:
                    logger.debug(f"Failed to connect to device via Wi-Fi SSH: {e}")
                    continue

        return None, None, None

    async def transfer_files(
        self,
        files: Iterable[Path],
        device: Device,
        destination: Path | None = None,
    ) -> TransferResult:
        """Transfer files to the specified device.

        Selects the best backend and copies files.

        Args:
            files: List of file paths to transfer.
            device: Target Device object.
            destination: Optional custom destination path on the device.
                         If None, uses DeviceStorageLayout default path.

        Returns:
            TransferResult with success status and details.
        """
        backend, method, conn_ctx = await self._select_backend(device)
        if not backend or not method:
            return TransferResult(
                success=False,
                errors=["No compatible transfer method found for this device's capabilities."]
            )

        layout = DeviceStorageLayout()
        dest_dir = destination or Path(layout.default_destination)

        file_list = [Path(f) for f in files]
        start_time = time.monotonic()
        total_bytes = sum(f.stat().st_size for f in file_list if f.exists())

        try:
            logger.info(f"Transferring {len(file_list)} files using {method.display_name}...")
            await backend.upload(file_list, dest_dir)
            duration = max(0.1, time.monotonic() - start_time)

            return TransferResult(
                method=method,
                success=True,
                files_transferred=len(file_list),
                bytes_transferred=total_bytes,
                duration=duration,
            )
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return TransferResult(
                method=method,
                success=False,
                errors=[str(e)]
            )
        finally:
            # Clean up backend mounts or ssh tunnels
            if backend is not None and hasattr(backend, "unmount"):
                try:
                    await backend.unmount()
                except Exception as e:
                    logger.debug(f"Cleanup unmount failed: {e}")
            if method == TransferMethod.USB_SSH:
                try:
                    await self.usb_ssh_manager.stop()
                except Exception as e:
                    logger.debug(f"Failed to stop USB SSH tunnel: {e}")
