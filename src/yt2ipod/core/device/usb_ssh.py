"""USB-SSH tunnel orchestration via iproxy (Phase 12).

Manages creating local-to-device SSH forwarding tunnels over USB using usbmuxd / iproxy.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import Optional

from yt2ipod.core.models.errors import ProcessExecutionError
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)


class USBSSHManager:
    """Manages local port forwarding to connected iOS devices via USB (iproxy)."""

    def __init__(self, iproxy_cmd: str = "iproxy") -> None:
        self.iproxy_cmd = iproxy_cmd
        self._proc: Optional[subprocess.Popen] = None

    def iproxy_available(self) -> bool:
        """Check if the iproxy binary is available on the system."""
        return shutil.which(self.iproxy_cmd) is not None

    async def is_port_open(self, host: str, port: int, timeout: float = 0.5) -> bool:
        """Asynchronously check if a local port is open and accepting TCP connections."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def start_iproxy(
        self, udid: str | None, local_port: int = 2222, device_port: int = 22
    ) -> None:
        """Start the iproxy process in the background.

        Args:
            udid: Unique device identifier.
            local_port: Local port to listen on.
            device_port: Target port on the device (typically 22 for SSH).
        """
        if not self.iproxy_available():
            raise ProcessExecutionError(
                "iproxy is not installed or not in PATH.",
                exit_code=127,
                stderr="iproxy not found"
            )

        # Stop any existing iproxy first
        await self.stop()

        cmd = [self.iproxy_cmd, str(local_port), str(device_port)]
        if udid:
            cmd.extend(["-u", udid])

        logger.info(f"Starting iproxy: {' '.join(cmd)}")
        try:
            # We start the process using Popen so it runs in the background.
            # Start in a new session so it doesn't receive signals meant for the parent.
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            raise ProcessExecutionError(
                f"Failed to spawn iproxy process: {e}",
                exit_code=1,
                stderr=str(e)
            ) from e

        # Wait for the port to become active (up to 2 seconds)
        for _ in range(20):
            await asyncio.sleep(0.1)
            if await self.is_port_open("127.0.0.1", local_port, timeout=0.1):
                logger.info(f"iproxy successfully bound to local port {local_port}")
                return

        # If we got here, iproxy failed to bind or start correctly
        await self.stop()
        raise ProcessExecutionError(
            f"iproxy process started but failed to bind local port {local_port} within timeout.",
            exit_code=1,
            stderr="Port bind timeout"
        )

    async def stop(self) -> None:
        """Terminate the running iproxy background process."""
        if not self._proc:
            return

        logger.info("Stopping iproxy background process...")
        try:
            self._proc.terminate()
            # Wait briefly for termination
            for _ in range(10):
                if self._proc.poll() is not None:
                    break
                await asyncio.sleep(0.1)

            if self._proc.poll() is None:
                logger.warning("iproxy did not terminate, sending SIGKILL...")
                self._proc.kill()
        except Exception as e:
            logger.debug(f"Error during iproxy termination: {e}")
        finally:
            self._proc = None

    async def ensure_ssh_over_usb(
        self, udid: str | None, local_port: int = 2222, device_port: int = 22
    ) -> tuple[str, int, subprocess.Popen | None]:
        """Ensure SSH over USB is active.

        If the port is already open (e.g. from an external forwarder), reuse it.
        Otherwise, launch our own iproxy tunnel.

        Returns:
            Tuple of (host, port, process).
        """
        host = "127.0.0.1"

        # Check if the port is already active
        if await self.is_port_open(host, local_port):
            logger.debug(f"Local port {local_port} already open. Reusing existing tunnel.")
            return host, local_port, None

        # Start our own iproxy
        await self.start_iproxy(udid, local_port, device_port)
        return host, local_port, self._proc
