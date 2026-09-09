"""User-level `launchd` automation (Phase 7).

Two clearly separate concerns: `build_plist`/`write_plist` are pure/
file-only and always safe to call (writing the same inputs twice produces
byte-identical output — idempotent by construction, via `plistlib.dumps`
rather than hand-built XML for correct escaping). `bootstrap`/`bootout`/
`is_loaded` actually shell out to `launchctl` to register, unregister, or
query the job with the running `launchd` — real, persistent, machine-level
actions, kept in their own functions so a caller (the `setup` CLI command)
can choose to write the plist without necessarily loading it, and so tests
can exercise the plist-generation logic without ever invoking a real
`launchctl`.

Per the roadmap: `StartInterval` is always present (Phase 7's "periodic
scan as the reliable fallback to folder events" — the thing to actually
trust); `WatchPaths` is added only in `schedule_mode == "monitoring"` for
faster-than-periodic triggering. Coalescing/overlap prevention is already
handled at the application layer (`io_utils.ScanLock`, used by
`scheduling.run_scan`), not re-implemented here.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .io_utils import atomic_write

LABEL = "com.voicememoarchive.scan"


def plist_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def default_log_path() -> Path:
    return Path.home() / "Library/Logs/Voice Memo Archive/scan.log"


def build_plist(
    *,
    config_path: Path,
    state_path: Path,
    scan_interval_seconds: int,
    watch_recordings_path: Path | None,
    log_path: Path,
    python_executable: str | None = None,
) -> dict:
    """Build the plist content as a plain dict, ready for `plistlib.dumps`.

    `watch_recordings_path` is None for `schedule_mode == "scheduled"` —
    the resulting plist omits `WatchPaths` entirely rather than watching
    nothing.
    """
    program_arguments = [
        python_executable or sys.executable,
        "-m",
        "voice_memo_archive.cli",
        "scan",
        "--config",
        str(config_path),
        "--state",
        str(state_path),
    ]
    plist: dict = {
        "Label": LABEL,
        "ProgramArguments": program_arguments,
        "StartInterval": scan_interval_seconds,
        "RunAtLoad": True,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }
    if watch_recordings_path is not None:
        plist["WatchPaths"] = [str(watch_recordings_path)]
    return plist


def write_plist(path: Path, plist: dict) -> None:
    atomic_write(path, plistlib.dumps(plist))


def install(
    *,
    config_path: Path,
    state_path: Path,
    recordings_source: Path,
    schedule_mode: str,
    scan_interval_seconds: int,
    python_executable: str | None = None,
) -> Path:
    """Write the plist file (idempotent), without loading it into launchd.

    Returns the path written. Loading it — a real, persistent registration
    with the running `launchd` — is `bootstrap`'s job, deliberately kept
    separate; see this module's docstring.
    """
    watch_path = recordings_source if schedule_mode == "monitoring" else None
    plist = build_plist(
        config_path=config_path,
        state_path=state_path,
        scan_interval_seconds=scan_interval_seconds,
        watch_recordings_path=watch_path,
        log_path=default_log_path(),
        python_executable=python_executable,
    )
    path = plist_path()
    write_plist(path, plist)
    return path


def _domain_target() -> str:
    return f"gui/{os.getuid()}"


def bootstrap(path: Path) -> None:
    """Load `path` into the running launchd. A real, persistent system change."""
    subprocess.run(["launchctl", "bootstrap", _domain_target(), str(path)], check=True)


def bootout() -> None:
    """Unload this job from the running launchd, if loaded. Never raises if it wasn't."""
    subprocess.run(
        ["launchctl", "bootout", f"{_domain_target()}/{LABEL}"],
        check=False,
        capture_output=True,
    )


def is_loaded() -> bool | None:
    """True/False if launchctl could answer, None if it couldn't be asked at all.

    A missing `launchctl` (non-macOS, e.g. this project's own CI) is
    reported as unknown, not as "not loaded" — those are different facts.
    """
    try:
        result = subprocess.run(
            ["launchctl", "print", f"{_domain_target()}/{LABEL}"],
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    return result.returncode == 0
