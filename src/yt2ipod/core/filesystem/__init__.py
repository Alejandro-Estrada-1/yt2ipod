"""Filesystem abstraction for device access."""

from yt2ipod.core.filesystem.backend import (
    FileSystemBackend,
    IfuseAFCBackend,
    LocalBackend,
    SSHBackend,
)

__all__ = ["FileSystemBackend", "LocalBackend", "IfuseAFCBackend", "SSHBackend"]
