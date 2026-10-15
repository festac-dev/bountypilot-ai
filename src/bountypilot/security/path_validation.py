"""Filesystem safety: restrictive permissions and secure temp files."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


def ensure_directory(path: Path, mode: int = 0o700) -> Path:
    """Create a directory with restrictive permissions, idempotently."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(mode)
    except OSError:
        pass  # Some filesystems (Termux shared storage) do not honour chmod.
    return path


@contextmanager
def secure_temp_file(suffix: str = ".tmp", directory: Optional[Path] = None) -> Iterator[Path]:
    """Yield a securely created temp file (0600) removed afterwards."""
    fd, name = tempfile.mkstemp(suffix=suffix, dir=str(directory) if directory else None)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        os.close(fd)
        yield Path(name)
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def write_private_file(path: Path, content: str) -> Path:
    """Atomically write a file readable only by the owner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    try:
        tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    os.replace(tmp, path)
    return path
