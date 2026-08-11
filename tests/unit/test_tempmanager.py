"""Unit tests for TemporaryFileManager."""

import os
from pathlib import Path

import pytest

from yt2ipod.core.cleanup.manager import TemporaryFileManager
from yt2ipod.core.models.errors import CleanupError
from yt2ipod.platform.detection import get_temp_directory


def test_default_temp_dir_exists():
    td = get_temp_directory()
    assert isinstance(td, Path)
    assert td.exists()


def test_create_and_cleanup_file(tmp_path):
    manager = TemporaryFileManager(base_dir=tmp_path, keep_temp=False)
    f = manager.create_temp_file(suffix=".dat")
    assert f.exists()
    assert f in manager.registered_files
    manager.cleanup()
    assert not f.exists()
    assert len(manager.registered_files) == 0


def test_keep_temp_flag(tmp_path):
    manager = TemporaryFileManager(base_dir=tmp_path, keep_temp=True)
    f = manager.create_temp_file(suffix=".dat")
    assert f.exists()
    manager.cleanup()
    assert f.exists()
    # clean up manually so we don't leak files
    f.unlink()


def test_register_only_under_base(tmp_path, tmp_path_factory):
    manager = TemporaryFileManager(base_dir=tmp_path, keep_temp=False)
    # create a file outside base
    other_dir = tmp_path_factory.mktemp("other")
    other = other_dir / "outside.txt"
    other.write_text("outside contents")
    
    manager.register(other)
    assert other not in manager.registered_files
    
    inside = manager.create_temp_file()
    assert inside in manager.registered_files
    
    manager.cleanup()
    assert other.exists()  # outside file is safe
    assert not inside.exists()
