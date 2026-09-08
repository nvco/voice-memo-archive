"""Atomic file writes and cross-invocation scan locking.

Both primitives are filesystem-only and have no dependency on the CLI or
`launchd`, so they can be exercised directly in tests (Phase 2 exit
criterion: "The scan lock and error taxonomy are testable independently of
the CLI or launchd.").
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from .errors import ArchiveError, ErrorCategory, ScanLockHeldError
from .paths import redact_home_path


def atomic_write(path: Path, data: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write `data` to `path` so a reader never observes a partial file.

    Writes to a temp file in the same directory (so the final `os.replace`
    is same-filesystem and therefore atomic), fsyncs it, then renames it
    over the target. An interrupted write leaves the original file (if any)
    untouched and the temp file orphaned, never a truncated target.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, mode, encoding=None if mode == "wb" else encoding) as tmp_file:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise ArchiveError(
            ErrorCategory.ARCHIVE_WRITE_FAILED,
            "failed to write file atomically",
            detail={"path": redact_home_path(path), "errno": exc.errno},
        ) from exc


class ScanLock:
    """An exclusive, PID-stamped lock file guarding one scan at a time.

    A lock held by a process that is no longer running is treated as stale
    and reclaimed automatically — a crashed prior scan must not permanently
    block future scans.
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._acquired = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._create_lock_file()
        except FileExistsError:
            if self._is_stale():
                with contextlib.suppress(FileNotFoundError):
                    self.lock_path.unlink()
                self._create_lock_file()
            else:
                holder_pid = self._read_holder_pid()
                raise ScanLockHeldError(
                    "a scan is already in progress",
                    detail={"path": redact_home_path(self.lock_path), "holder_pid": holder_pid},
                ) from None
        self._acquired = True

    def release(self) -> None:
        if self._acquired:
            with contextlib.suppress(FileNotFoundError):
                self.lock_path.unlink()
            self._acquired = False

    def _create_lock_file(self) -> None:
        fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as lock_file:
            lock_file.write(str(os.getpid()))

    def _read_holder_pid(self) -> int | None:
        try:
            return int(self.lock_path.read_text().strip())
        except (OSError, ValueError):
            return None

    def _is_stale(self) -> bool:
        holder_pid = self._read_holder_pid()
        if holder_pid is None:
            return True
        try:
            os.kill(holder_pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # A live process we don't own is holding it — not stale.
            return False
        return False

    def __enter__(self) -> ScanLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
