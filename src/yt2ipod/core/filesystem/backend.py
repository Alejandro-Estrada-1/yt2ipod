"""FileSystem backends for device file operations (Phase 10).

Defines an abstract FileSystemBackend and implement local, ifuse-mounted (AFC),
and SSH/SCP-based remote filesystem wrappers.
"""

from __future__ import annotations

import abc
import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from yt2ipod.core.models.errors import FileSystemError
from yt2ipod.utils.logging import get_logger
from yt2ipod.utils.runner import ProcessRunner

logger = get_logger(__name__)


class FileSystemBackend(abc.ABC):
    """Abstract base class representing a target filesystem."""

    @abc.abstractmethod
    async def list(self, path: Path) -> list[Path]:
        """List files in the given directory."""

    @abc.abstractmethod
    async def upload(self, local_paths: Iterable[Path], remote_dir: Path) -> None:
        """Upload multiple local files to a directory on the target filesystem."""

    @abc.abstractmethod
    async def download(self, remote_path: Path, local_path: Path) -> None:
        """Download a file from the target filesystem to local."""

    @abc.abstractmethod
    async def delete(self, remote_path: Path) -> None:
        """Delete a file or directory on the target filesystem."""

    @abc.abstractmethod
    async def mkdir(self, remote_dir: Path) -> None:
        """Create a directory on the target filesystem."""

    @abc.abstractmethod
    async def exists(self, remote_path: Path) -> bool:
        """Check if a path exists on the target filesystem."""


class LocalBackend(FileSystemBackend):
    """Local filesystem implementation (primarily for local transfers or testing)."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def _resolve(self, p: Path) -> Path:
        # Prevent directory traversal attacks
        resolved = (self.root_dir / p).resolve()
        if self.root_dir not in resolved.parents and resolved != self.root_dir:
            raise FileSystemError("Attempted directory traversal outside root directory.")
        return resolved

    async def list(self, path: Path) -> list[Path]:
        try:
            target = self._resolve(path)
            if not target.exists():
                return []
            return list(target.iterdir())
        except Exception as e:
            raise FileSystemError(f"Failed to list directory {path}: {e}") from e

    async def upload(self, local_paths: Iterable[Path], remote_dir: Path) -> None:
        try:
            target_dir = self._resolve(remote_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            for lp in local_paths:
                dest = target_dir / lp.name
                shutil.copy2(lp, dest)
        except Exception as e:
            raise FileSystemError(f"Failed to upload files: {e}") from e

    async def download(self, remote_path: Path, local_path: Path) -> None:
        try:
            source = self._resolve(remote_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, local_path)
        except Exception as e:
            raise FileSystemError(f"Failed to download file {remote_path}: {e}") from e

    async def delete(self, remote_path: Path) -> None:
        try:
            target = self._resolve(remote_path)
            if target.is_file() or target.is_symlink():
                target.unlink(missing_ok=True)
            elif target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
        except Exception as e:
            raise FileSystemError(f"Failed to delete {remote_path}: {e}") from e

    async def mkdir(self, remote_dir: Path) -> None:
        try:
            self._resolve(remote_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileSystemError(f"Failed to create directory {remote_dir}: {e}") from e

    async def exists(self, remote_path: Path) -> bool:
        try:
            return self._resolve(remote_path).exists()
        except Exception:
            return False


class IfuseAFCBackend(FileSystemBackend):
    """Mounts the device via ifuse, performing filesystem operations locally.

    Automates mount and unmount operations using ifuse and fusermount.
    """

    def __init__(self, mount_point: Path, udid: str | None = None) -> None:
        self.mount_point = Path(mount_point).resolve()
        self.udid = udid
        self._mounted = False
        self._local = LocalBackend(self.mount_point)

    async def mount(self) -> None:
        """Mount the device to the mount point."""
        if not shutil.which("ifuse"):
            raise FileSystemError("ifuse is not installed or not in PATH.")

        self.mount_point.mkdir(parents=True, exist_ok=True)
        cmd = ["ifuse"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append(str(self.mount_point))

        try:
            await ProcessRunner.run(cmd, check=True)
            self._mounted = True
            logger.info(f"Successfully mounted iOS device to {self.mount_point}")
        except Exception as e:
            raise FileSystemError(f"ifuse mount failed: {e}") from e

    async def unmount(self) -> None:
        """Unmount the device from the mount point."""
        if not self._mounted:
            return

        # Attempt fusermount -u first (Linux), then fallback to umount (macOS)
        unmount_bin = "fusermount" if shutil.which("fusermount") else "umount"
        cmd = [unmount_bin]
        if unmount_bin == "fusermount":
            cmd.append("-u")
        cmd.append(str(self.mount_point))

        try:
            await ProcessRunner.run(cmd, check=True)
            self._mounted = False
            logger.info("Successfully unmounted iOS device.")
        except Exception as e:
            logger.warning(f"Failed to unmount iOS device: {e}. Force clean might be needed.")

    async def _ensure_mounted(self) -> None:
        if not self._mounted:
            await self.mount()

    async def list(self, path: Path) -> list[Path]:
        await self._ensure_mounted()
        return await self._local.list(path)

    async def upload(self, local_paths: Iterable[Path], remote_dir: Path) -> None:
        await self._ensure_mounted()
        await self._local.upload(local_paths, remote_dir)

    async def download(self, remote_path: Path, local_path: Path) -> None:
        await self._ensure_mounted()
        await self._local.download(remote_path, local_path)

    async def delete(self, remote_path: Path) -> None:
        await self._ensure_mounted()
        await self._local.delete(remote_path)

    async def mkdir(self, remote_dir: Path) -> None:
        await self._ensure_mounted()
        await self._local.mkdir(remote_dir)

    async def exists(self, remote_path: Path) -> bool:
        await self._ensure_mounted()
        return await self._local.exists(remote_path)


class SSHBackend(FileSystemBackend):
    """Interacts with the device using standard SSH/SCP commands."""

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "mobile",
        identity_file: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.identity_file = identity_file

    def _user_host(self) -> str:
        return f"{self.username}@{self.host}"

    def _ssh_cmd(self, remote_cmd: str) -> list[str]:
        cmd = ["ssh", "-p", str(self.port), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no"]
        if self.identity_file:
            cmd.extend(["-i", str(self.identity_file)])
        cmd.extend([self._user_host(), remote_cmd])
        return cmd

    def _scp_cmd(self, local_paths: list[str], remote_dest: str) -> list[str]:
        cmd = ["scp", "-P", str(self.port), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no"]
        if self.identity_file:
            cmd.extend(["-i", str(self.identity_file)])
        cmd.extend(local_paths)
        cmd.append(remote_dest)
        return cmd

    async def list(self, path: Path) -> list[Path]:
        # ls -1 lists one file per line
        cmd = self._ssh_cmd(f"ls -1 '{path}'")
        try:
            result = await ProcessRunner.run(cmd)
            if not result.success:
                # If directory does not exist or ls fails
                return []
            stdout = result.stdout.strip()
            return [Path(line.strip()) for line in stdout.splitlines() if line.strip()]
        except Exception as e:
            raise FileSystemError(f"SSH list failed: {e}") from e

    async def upload(self, local_paths: Iterable[Path], remote_dir: Path) -> None:
        # First ensure target directory exists
        await self.mkdir(remote_dir)

        paths = [str(lp) for lp in local_paths]
        remote_dest = f"{self._user_host()}:'{remote_dir}'"
        cmd = self._scp_cmd(paths, remote_dest)
        try:
            await ProcessRunner.run(cmd, check=True)
        except Exception as e:
            raise FileSystemError(f"SSH/SCP upload failed: {e}") from e

    async def download(self, remote_path: Path, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        remote_src = f"{self._user_host()}:'{remote_path}'"
        cmd = self._scp_cmd([remote_src], str(local_path))
        try:
            await ProcessRunner.run(cmd, check=True)
        except Exception as e:
            raise FileSystemError(f"SSH/SCP download failed: {e}") from e

    async def delete(self, remote_path: Path) -> None:
        cmd = self._ssh_cmd(f"rm -rf '{remote_path}'")
        try:
            await ProcessRunner.run(cmd, check=True)
        except Exception as e:
            raise FileSystemError(f"SSH delete failed: {e}") from e

    async def mkdir(self, remote_dir: Path) -> None:
        cmd = self._ssh_cmd(f"mkdir -p '{remote_dir}'")
        try:
            await ProcessRunner.run(cmd, check=True)
        except Exception as e:
            raise FileSystemError(f"SSH mkdir failed: {e}") from e

    async def exists(self, remote_path: Path) -> bool:
        # [ -e path ] returns 0 if exists, else non-zero
        cmd = self._ssh_cmd(f"[ -e '{remote_path}' ]")
        try:
            result = await ProcessRunner.run(cmd)
            return result.success
        except Exception:
            return False
