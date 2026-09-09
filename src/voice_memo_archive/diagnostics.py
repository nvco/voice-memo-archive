"""Setup and `doctor`-style diagnostics (Phase 7).

Every check here is read-only (no config/state/archive mutation, no
directory creation) and returns a factual, transcript-free result — the
same message-safety discipline `errors.py` establishes: no transcript
text, no recording titles, any path redacted via `paths.redact_home_path`
before it's ever included. `run_doctor` aggregates every check into one
report; `cli.py`'s `doctor` subcommand is a thin printer over it.
"""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from pathlib import Path

from . import config, launchd
from .errors import ConfigError, StateError
from .paths import redact_home_path
from .state import RecordingStatus, load_state


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def check_recordings_access(recordings_source: Path) -> CheckResult:
    """Explicitly distinguish the FDA-denied case from a generic access failure.

    macOS gives no programmatic prompt for Full Disk Access (confirmed in
    tasks/005-...md's Findings) — an EPERM here almost always means that,
    not a transient/generic OSError, so the message points at System
    Settings rather than reporting a bare "not found".
    """
    try:
        next(recordings_source.iterdir(), None)
    except FileNotFoundError:
        return CheckResult(
            "recordings_source",
            False,
            f"recordings folder not found: {redact_home_path(recordings_source)}",
        )
    except PermissionError as exc:
        if exc.errno == errno.EPERM:
            return CheckResult(
                "recordings_source",
                False,
                "Full Disk Access appears to be denied — grant it in System "
                "Settings > Privacy & Security > Full Disk Access, then try again.",
            )
        return CheckResult(
            "recordings_source",
            False,
            f"permission denied: {redact_home_path(recordings_source)}",
        )
    except OSError as exc:
        return CheckResult(
            "recordings_source", False, f"could not list recordings folder (errno {exc.errno})"
        )
    return CheckResult("recordings_source", True, "accessible")


def check_archive_root_writable(archive_root: Path) -> CheckResult:
    """Walk up to the nearest existing ancestor and check write access there.

    Never creates anything — `archive_root` itself may not exist yet
    before the first successful archive write, which is expected and not
    itself a problem as long as some existing ancestor is writable.
    """
    probe = archive_root
    while not probe.exists():
        if probe.parent == probe:
            break
        probe = probe.parent
    if not os.access(probe, os.W_OK):
        return CheckResult("archive_root", False, f"not writable: {redact_home_path(probe)}")
    return CheckResult("archive_root", True, "writable")


def check_config(config_path: Path) -> CheckResult:
    try:
        config.load_config(config_path)
    except ConfigError as exc:
        return CheckResult("config", False, str(exc))
    return CheckResult("config", True, "valid")


def check_state(state_path: Path) -> CheckResult:
    try:
        load_state(state_path)
    except StateError as exc:
        return CheckResult(
            "state", False, f"{exc} (will self-heal from the archive on the next scan)"
        )
    return CheckResult("state", True, "valid")


def check_scheduler() -> CheckResult:
    loaded = launchd.is_loaded()
    if loaded is None:
        return CheckResult("scheduler", True, "unknown (launchctl unavailable)")
    if loaded:
        return CheckResult("scheduler", True, "loaded")
    return CheckResult("scheduler", False, "not loaded — run `setup` to install automation")


def check_pending_work(state_path: Path) -> CheckResult:
    try:
        state = load_state(state_path)
    except StateError:
        return CheckResult("pending_work", True, "unknown (state unreadable)")
    counts: dict[str, int] = {}
    for record in state.recordings.values():
        counts[record.status.value] = counts.get(record.status.value, 0) + 1
    needs_attention = counts.get(RecordingStatus.NEEDS_ATTENTION.value, 0)
    conflicts = counts.get(RecordingStatus.CONFLICT.value, 0)
    ok = needs_attention == 0 and conflicts == 0
    detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing tracked yet"
    return CheckResult("pending_work", ok, detail)


def run_doctor(*, config_path: Path, state_path: Path) -> tuple[CheckResult, ...]:
    config_result = check_config(config_path)
    if config_result.ok:
        cfg = config.load_config(config_path)
        recordings_result = check_recordings_access(Path(cfg.recordings_source).expanduser())
        archive_root_result = check_archive_root_writable(Path(cfg.archive_root).expanduser())
    else:
        # An invalid config.json might be hiding a customized
        # recordings_source/archive_root — falling back to the global
        # defaults here would silently check the *wrong* folder rather
        # than admitting we don't actually know. Skip, don't guess.
        recordings_result = CheckResult("recordings_source", True, "skipped (config invalid)")
        archive_root_result = CheckResult("archive_root", True, "skipped (config invalid)")

    return (
        config_result,
        recordings_result,
        archive_root_result,
        check_state(state_path),
        check_scheduler(),
        check_pending_work(state_path),
    )
