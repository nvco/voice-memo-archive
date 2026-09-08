"""Filename parsing, date/timezone helpers, and path redaction.

Filename grammar is drawn from real-sample evidence in
`tasks/005-platform-feasibility-and-data-contract.md` ("Filename grammar"
and "Filename-less-ID case" findings): most recordings are named
`YYYYMMDD HHMMSS-<ID>.ext`; a recording that went through Voice Memos'
"add to existing recording" flow can have no `-<ID>` suffix, in which case
the canonical ID lives in an adjacent `<timestamp>.composition/
manifest.plist` sidecar instead (Phase 3's concern, not parsed here).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SUPPORTED_EXTENSIONS = frozenset({"m4a", "qta"})

_FILENAME_RE = re.compile(
    r"^(?P<date>\d{8}) (?P<time>\d{6})(?:-(?P<id>[^./]+))?\.(?P<ext>[A-Za-z0-9]+)$"
)


@dataclass(frozen=True)
class RecordingFilenameInfo:
    recorded_at: datetime  # naive, local time as encoded in the filename
    id_suffix: str | None  # None means: look up the ID via a composition sidecar
    extension: str  # lowercased, e.g. "m4a"


def parse_recording_filename(filename: str) -> RecordingFilenameInfo | None:
    """Parse a Voice Memos recording filename.

    Returns None if the filename doesn't match the known grammar or its
    extension isn't one of `SUPPORTED_EXTENSIONS` — callers use this to
    decide whether a file is even a discovery candidate, not to raise.
    """
    match = _FILENAME_RE.match(filename)
    if match is None:
        return None

    extension = match.group("ext").lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return None

    try:
        recorded_at = datetime.strptime(
            f"{match.group('date')} {match.group('time')}", "%Y%m%d %H%M%S"
        )
    except ValueError:
        return None

    return RecordingFilenameInfo(
        recorded_at=recorded_at,
        id_suffix=match.group("id"),
        extension=extension,
    )


def archive_date_parts(recorded_at: datetime) -> tuple[str, str, str]:
    """Zero-padded (year, month, day) strings for archive grouping."""
    return (
        f"{recorded_at.year:04d}",
        f"{recorded_at.month:02d}",
        f"{recorded_at.day:02d}",
    )


def attach_local_timezone(naive_dt: datetime) -> datetime:
    """Attach the system's local timezone to a naive datetime in place.

    A filename-derived timestamp carries no timezone. `datetime.astimezone()`
    on a naive datetime treats it as already being local time and only
    attaches `tzinfo` — it does not shift the wall-clock value. Do not call
    this on a datetime that isn't already naive-local.
    """
    if naive_dt.tzinfo is not None:
        raise ValueError("expected a naive datetime")
    return naive_dt.astimezone()


def redact_home_path(path: str | Path) -> str:
    """Collapse the user's home directory prefix to `~` for safe logging."""
    path_str = str(path)
    home_str = str(Path.home())
    if path_str == home_str:
        return "~"
    if path_str.startswith(home_str + "/"):
        return "~" + path_str[len(home_str) :]
    return path_str
