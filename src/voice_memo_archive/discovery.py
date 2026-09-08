"""File discovery and source metadata (Phase 3).

Enumerates the configured recordings folder read-only, applies the
exclusion list from tasks/005-...md's Findings, resolves each candidate's
dedup ID (including the composition-sidecar case for ID-less filenames —
see that file's "Filename-less-ID case" finding), and classifies each
candidate deterministically against previously recorded state.

This module never writes, renames, or deletes anything under the
recordings source — every filesystem call it makes is read-only
(`iterdir`, `stat`, opening a file/plist for reading).
"""

from __future__ import annotations

import plistlib
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import ArchiveError, ErrorCategory
from .paths import SUPPORTED_EXTENSIONS, parse_recording_filename, redact_home_path
from .state import RecordingState

# Non-candidate entries confirmed present in the configured Recordings
# folder (tasks/005-...md Findings) that discovery must skip rather than
# misclassify as malformed.
_EXCLUDED_DIR_NAMES = frozenset(
    {"Capture", "CaptureRecovery", ".CloudRecordings_SUPPORT", "CloudRecordings_ckAssets"}
)
_EXCLUDED_DB_FILE_NAMES = frozenset(
    {"CloudRecordings.db", "CloudRecordings.db-shm", "CloudRecordings.db-wal"}
)


class CandidateStatus(StrEnum):
    NEW = "new"  # no prior state entry for this ID
    UNCHANGED = "unchanged"  # fingerprint matches the prior state entry
    CHANGED = "changed"  # prior state entry exists, fingerprint differs
    MALFORMED_FILENAME = "malformed_filename"
    UNRESOLVABLE_ID = "unresolvable_id"
    DUPLICATE_ID = "duplicate_id"
    INACCESSIBLE = "inaccessible"
    UNSTABLE = "unstable"  # size/mtime changed between two reads (e.g. still downloading)


@dataclass(frozen=True)
class Candidate:
    path: Path
    status: CandidateStatus
    recording_id: str | None = None
    source_format: str | None = None
    recorded_at_iso: str | None = None  # naive local timestamp parsed from the filename
    size: int | None = None
    mtime: float | None = None
    detail: dict[str, object] | None = None


def _is_excluded(entry: Path) -> bool:
    if entry.is_dir():
        return entry.name in _EXCLUDED_DIR_NAMES or entry.name.endswith(".composition")
    return entry.name.endswith(".waveform") or entry.name in _EXCLUDED_DB_FILE_NAMES


def _resolve_composition_sidecar_id(recordings_source: Path, filename_stem: str) -> str | None:
    """Read `RCSavedRecordingUUID` from an ID-less recording's sidecar.

    Returns None if the sidecar or the expected key is missing/unreadable —
    callers must treat that as `UNRESOLVABLE_ID`, never guess a substitute.
    """
    manifest_path = recordings_source / f"{filename_stem}.composition" / "manifest.plist"
    try:
        with manifest_path.open("rb") as manifest_file:
            manifest = plistlib.load(manifest_file)
    except (OSError, plistlib.InvalidFileException):
        return None
    uuid = manifest.get("RCSavedRecordingUUID")
    return uuid if isinstance(uuid, str) and uuid else None


def _stat_with_stability_check(
    path: Path, *, stability_check_delay: float
) -> tuple[int, float] | None:
    """Two `stat()` reads separated by a short delay.

    Returns None if the two reads disagree (still being written/downloaded)
    or the file couldn't be stat'd at all is signaled by raising OSError,
    which callers catch separately to distinguish INACCESSIBLE from
    UNSTABLE.
    """
    first = path.stat()
    time.sleep(stability_check_delay)
    second = path.stat()
    if first.st_size != second.st_size or first.st_mtime != second.st_mtime:
        return None
    return (second.st_size, second.st_mtime)


def scan(
    recordings_source: Path,
    known_recordings: dict[str, RecordingState],
    *,
    stability_check_delay: float = 0.2,
) -> list[Candidate]:
    """Enumerate the recordings source and classify each candidate.

    Deterministic: entries are processed in sorted-name order regardless of
    filesystem iteration order, so repeated scans over unchanged input
    produce an identically ordered result.
    """
    try:
        entries = sorted(recordings_source.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        raise ArchiveError(
            ErrorCategory.SOURCE_UNREADABLE,
            "could not list the configured recordings folder",
            detail={"path": redact_home_path(recordings_source), "errno": exc.errno},
        ) from exc

    candidates: list[Candidate] = []
    for entry in entries:
        if _is_excluded(entry) or entry.is_dir():
            continue

        extension = entry.suffix.lstrip(".").lower()
        if extension not in SUPPORTED_EXTENSIONS:
            continue

        candidates.append(_classify(entry, known_recordings, stability_check_delay))

    return _flag_duplicate_ids(candidates)


def _classify(
    path: Path, known_recordings: dict[str, RecordingState], stability_check_delay: float
) -> Candidate:
    filename_info = parse_recording_filename(path.name)
    if filename_info is None:
        return Candidate(path=path, status=CandidateStatus.MALFORMED_FILENAME)

    recording_id = filename_info.id_suffix
    if recording_id is None:
        recording_id = _resolve_composition_sidecar_id(path.parent, path.stem)
    if recording_id is None:
        return Candidate(
            path=path,
            status=CandidateStatus.UNRESOLVABLE_ID,
            source_format=filename_info.extension,
            recorded_at_iso=filename_info.recorded_at.isoformat(),
        )

    try:
        fingerprint = _stat_with_stability_check(path, stability_check_delay=stability_check_delay)
    except OSError as exc:
        return Candidate(
            path=path,
            status=CandidateStatus.INACCESSIBLE,
            recording_id=recording_id,
            source_format=filename_info.extension,
            recorded_at_iso=filename_info.recorded_at.isoformat(),
            detail={"errno": exc.errno},
        )
    if fingerprint is None:
        return Candidate(
            path=path,
            status=CandidateStatus.UNSTABLE,
            recording_id=recording_id,
            source_format=filename_info.extension,
            recorded_at_iso=filename_info.recorded_at.isoformat(),
        )

    size, mtime = fingerprint
    prior = known_recordings.get(recording_id)
    if prior is None:
        status = CandidateStatus.NEW
    elif prior.source_size == size and prior.source_mtime == mtime:
        status = CandidateStatus.UNCHANGED
    else:
        status = CandidateStatus.CHANGED

    return Candidate(
        path=path,
        status=status,
        recording_id=recording_id,
        source_format=filename_info.extension,
        recorded_at_iso=filename_info.recorded_at.isoformat(),
        size=size,
        mtime=mtime,
    )


def _flag_duplicate_ids(candidates: list[Candidate]) -> list[Candidate]:
    ids_seen: dict[str, list[int]] = {}
    for index, candidate in enumerate(candidates):
        if candidate.recording_id is not None:
            ids_seen.setdefault(candidate.recording_id, []).append(index)

    duplicate_indices = {
        index for indices in ids_seen.values() if len(indices) > 1 for index in indices
    }
    if not duplicate_indices:
        return candidates

    result = list(candidates)
    for index in duplicate_indices:
        original = result[index]
        siblings = [
            redact_home_path(candidates[i].path)
            for i in ids_seen[original.recording_id]
            if i != index
        ]
        result[index] = Candidate(
            path=original.path,
            status=CandidateStatus.DUPLICATE_ID,
            recording_id=original.recording_id,
            source_format=original.source_format,
            recorded_at_iso=original.recorded_at_iso,
            size=original.size,
            mtime=original.mtime,
            detail={"duplicate_of": siblings},
        )
    return result
