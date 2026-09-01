"""Temporary file management and cleanup (Phase 8).

Manages creation of temporary files and directories under a platform-appropriate
temp folder, keeping track of them for safe cleanup.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from yt2ipod.core.models.errors import CleanupError
from yt2ipod.platform.detection import get_temp_directory
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)


class TemporaryFileManager:
    """Manages temporary files and directories, ensuring they are deleted.

    Keeps track of all files and directories created or explicitly registered,
    and cleans them up on demand. Safe: only deletes registered files/dirs
    nested within the configured base temporary directory.
    """

    def __init__(self, base_dir: Path | None = None, keep_temp: bool = False) -> None:
        """Initialize the manager.

        Args:
            base_dir: Optional base temporary directory. If None, resolves
                      via platform detection.
            keep_temp: If True, cleanup() will not delete anything (useful for debug).
        """
        self.base_dir = (base_dir or get_temp_directory()).resolve()
        self.keep_temp = keep_temp
        self._registered_files: list[Path] = []
        self._registered_dirs: list[Path] = []

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create base temp directory {self.base_dir}: {e}. Falling back to std temp.")
            self.base_dir = Path(tempfile.gettempdir()).resolve()

    def _is_safe_path(self, path: Path) -> bool:
        """Verify that the path is nested inside the base_dir to prevent accidental deletion."""
        try:
            resolved_path = path.resolve()
            return self.base_dir in resolved_path.parents or resolved_path == self.base_dir
        except Exception:
            return False

    def create_temp_file(self, suffix: str = "") -> Path:
        """Create a new temporary file and register it.

        Args:
            suffix: File suffix (e.g. '.jpg', '.mp3').

        Returns:
            Path to the created file.
        """
        filename = f"yt2ipod-{uuid.uuid4().hex}{suffix}"
        path = self.base_dir / filename
        try:
            # Create file with safe permissions (owner readable/writable only)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        except Exception as e:
            raise CleanupError(f"Failed to create temporary file {path.name}: {e}") from e

        resolved = path.resolve()
        self._registered_files.append(resolved)
        return resolved

    def create_temp_dir(self, prefix: str = "yt2ipod-") -> Path:
        """Create a new temporary directory and register it.

        Args:
            prefix: Prefix for the directory name.

        Returns:
            Path to the created directory.
        """
        dirname = f"{prefix}{uuid.uuid4().hex}"
        path = self.base_dir / dirname
        try:
            path.mkdir(parents=True, exist_ok=False)
        except Exception as e:
            raise CleanupError(f"Failed to create temporary directory {path.name}: {e}") from e

        resolved = path.resolve()
        self._registered_dirs.append(resolved)
        return resolved

    def register(self, path: Path) -> None:
        """Register an existing file or directory for cleanup.

        Must be nested under the base temporary directory.
        """
        resolved = Path(path).resolve()
        if not resolved.exists():
            return

        if not self._is_safe_path(resolved):
            logger.warning(f"Path {resolved} is not inside base temp dir {self.base_dir}. Skipping registration.")
            return

        if resolved.is_file():
            if resolved not in self._registered_files:
                self._registered_files.append(resolved)
        elif resolved.is_dir():
            if resolved not in self._registered_dirs:
                self._registered_dirs.append(resolved)

    def cleanup(self) -> None:
        """Clean up all registered files and directories.

        If keep_temp is True, skip deletion.
        """
        if self.keep_temp:
            logger.info("keep_temp is enabled; skipping temporary file cleanup.")
            return

        # Clean up files first
        for file_path in list(self._registered_files):
            try:
                if file_path.is_file() or file_path.is_symlink():
                    file_path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to delete temp file {file_path}: {e}")
        self._registered_files.clear()

        # Clean up directories (deepest first to ensure subdirs are empty)
        sorted_dirs = sorted(self._registered_dirs, key=lambda p: len(p.parts), reverse=True)
        for dir_path in sorted_dirs:
            try:
                if dir_path.is_dir():
                    # rmdir only removes empty directories. To be extra safe,
                    # we only remove them if empty or use rmtree if absolutely necessary,
                    # but spec says "safe cleanup: never rm -rf on arbitrary paths".
                    # Let's use shutil.rmtree but only since it is checked safe.
                    if self._is_safe_path(dir_path):
                        shutil.rmtree(dir_path, ignore_errors=True)
            except Exception as e:
                logger.debug(f"Failed to delete temp directory {dir_path}: {e}")
        self._registered_dirs.clear()

    @property
    def registered_files(self) -> list[Path]:
        """List of currently registered files."""
        return list(self._registered_files)

    @property
    def registered_dirs(self) -> list[Path]:
        """List of currently registered directories."""
        return list(self._registered_dirs)
