import os
import threading
from pathlib import Path

import pytest

from voice_memo_archive.errors import ArchiveError, ScanLockHeldError
from voice_memo_archive.io_utils import ScanLock, atomic_write


def test_atomic_write_creates_file(tmp_path: Path):
    target = tmp_path / "sub" / "config.json"
    atomic_write(target, '{"a": 1}')
    assert target.read_text() == '{"a": 1}'


def test_atomic_write_leaves_no_temp_file_behind(tmp_path: Path):
    target = tmp_path / "config.json"
    atomic_write(target, "data")
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_atomic_write_never_leaves_partial_file_on_failure(tmp_path: Path, monkeypatch):
    target = tmp_path / "config.json"
    target.write_text("original")

    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", boom)
    with pytest.raises(ArchiveError):
        atomic_write(target, "new data")
    assert target.read_text() == "original"
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_scan_lock_blocks_second_acquire(tmp_path: Path):
    lock_path = tmp_path / "scan.lock"
    lock = ScanLock(lock_path)
    lock.acquire()
    try:
        with pytest.raises(ScanLockHeldError):
            ScanLock(lock_path).acquire()
    finally:
        lock.release()


def test_scan_lock_context_manager_releases_on_exit(tmp_path: Path):
    lock_path = tmp_path / "scan.lock"
    with ScanLock(lock_path):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_scan_lock_reclaims_stale_lock_from_dead_pid(tmp_path: Path):
    lock_path = tmp_path / "scan.lock"
    # A PID essentially guaranteed not to be alive right now.
    dead_pid = 2**30
    lock_path.write_text(str(dead_pid))

    lock = ScanLock(lock_path)
    lock.acquire()
    try:
        assert lock_path.read_text().strip() == str(os.getpid())
    finally:
        lock.release()


def test_scan_lock_is_process_independent_of_cli(tmp_path: Path):
    # Exercises the lock with no CLI/launchd involved at all, per the
    # Phase 2 exit criterion that it be independently testable.
    lock_path = tmp_path / "scan.lock"
    results: dict[str, bool] = {}

    def try_second_acquire():
        try:
            ScanLock(lock_path).acquire()
            results["second_acquired"] = True
        except ScanLockHeldError:
            results["second_acquired"] = False

    with ScanLock(lock_path):
        thread = threading.Thread(target=try_second_acquire)
        thread.start()
        thread.join(timeout=2)

    assert results["second_acquired"] is False
