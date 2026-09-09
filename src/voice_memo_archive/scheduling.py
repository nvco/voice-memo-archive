"""Scan orchestration, retries, and recovery (Phase 6).

Drives one scan under `io_utils.ScanLock`: calls `discovery.scan()`, then
for each candidate with a resolvable recording ID, attempts
`extraction.extract_transcript()` and `archive.write_archive_entry()` and
records the outcome as a `state.RecordingState`. The CLI (`cli.py`) and,
eventually, `launchd` (Phase 7) are both thin callers of `run_scan` — the
workflow itself lives here, once, not duplicated per caller.

Status mapping (see `tasks/030-...md` for the full reasoning):

- `discovery.CandidateStatus.UNCHANGED` against a prior `PROCESSED`/
  `SKIPPED_EMPTY`/`SKIPPED_NO_TRANSCRIPT`/`ACKNOWLEDGED`/`CONFLICT` record
  is left completely untouched — satisfies "normal scans do not parse
  stable successful recordings again."
- `NEW`/`CHANGED` (or an `UNCHANGED` `FAILED` record whose retry delay has
  elapsed) triggers a fresh extraction attempt.
- A candidate with no resolvable recording ID (`MALFORMED_FILENAME`,
  `UNRESOLVABLE_ID`) is never written into `state.recordings` at all —
  there is no ID to key a record on — and is instead reported directly in
  the returned `ScanSummary.unidentified`, so it is surfaced every scan for
  as long as the underlying file exists rather than silently dropped.
- `DUPLICATE_ID`, and an `ArchiveError(ARCHIVE_CONFLICT, ...)` raised by
  `write_archive_entry`, both become `RecordingStatus.CONFLICT`.
- `ExtractionStatus.EMPTY` becomes `RecordingStatus.PENDING` the first
  time, and only becomes `RecordingStatus.SKIPPED_EMPTY` once the *same*
  source fingerprint reproduces `EMPTY` on a later scan (the roadmap's
  "require stability across scans" rule) — see `_handle_empty`.
- `ExtractionStatus.ABSENT`/`UNSUPPORTED` become `SKIPPED_NO_TRANSCRIPT`
  (a stable fact, not a transient failure to retry).
- `ExtractionStatus.UNREADABLE`/`MALFORMED`/`INCOMPLETE`,
  `CandidateStatus.INACCESSIBLE`/`UNSTABLE`, and an unexpected
  `ArchiveError` (e.g. `ARCHIVE_WRITE_FAILED`) are all transient-shaped
  failures: `RecordingStatus.FAILED` with increasing retry spacing
  (`RETRY_DELAYS`), escalating to `RecordingStatus.NEEDS_ATTENTION` once
  exhausted.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from . import archive, config, discovery, extraction
from .errors import ArchiveError, ErrorCategory, StateError
from .io_utils import ScanLock
from .paths import attach_local_timezone, format_utc_iso, redact_home_path
from .state import RecordingState, RecordingStatus, State, load_state, save_state

# Three spaced, increasing-delay retry opportunities per
# `tasks/000-initial-build.md` Phase 6, before a transient failure becomes
# `needs_attention`. Concrete values are this phase's own judgment call —
# the roadmap specifies the shape ("spaced, increasing"), not the numbers.
RETRY_DELAYS: tuple[timedelta, ...] = (
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
)

_ACKNOWLEDGEABLE = frozenset({RecordingStatus.NEEDS_ATTENTION})
_RETRYABLE = frozenset(
    {RecordingStatus.FAILED, RecordingStatus.NEEDS_ATTENTION, RecordingStatus.CONFLICT}
)
# Prior statuses an UNCHANGED fingerprint leaves completely untouched —
# nothing about a stable source can change a stable, already-resolved fact.
_STABLE_UNCHANGED_STATUSES = frozenset(
    {
        RecordingStatus.PROCESSED,
        RecordingStatus.SKIPPED_EMPTY,
        RecordingStatus.SKIPPED_NO_TRANSCRIPT,
        RecordingStatus.NEEDS_ATTENTION,
        RecordingStatus.ACKNOWLEDGED,
        RecordingStatus.CONFLICT,
    }
)

_EXTRACTION_FAILURE_CATEGORY = {
    extraction.ExtractionStatus.UNREADABLE: ErrorCategory.SOURCE_UNREADABLE,
    extraction.ExtractionStatus.MALFORMED: ErrorCategory.TRANSCRIPT_MALFORMED,
    extraction.ExtractionStatus.INCOMPLETE: ErrorCategory.TRANSCRIPT_INCOMPLETE,
}


@dataclasses.dataclass(frozen=True)
class UnidentifiedEntry:
    """A discovered file with no resolvable recording ID — never persisted."""

    path: str  # already redacted
    status: str


@dataclasses.dataclass(frozen=True)
class ScanSummary:
    result_counts: dict[str, int]
    unidentified: tuple[UnidentifiedEntry, ...]
    last_error_category: str | None


def _first_seen(prior: RecordingState | None, now_str: str) -> str:
    if prior is not None and prior.first_seen_at is not None:
        return prior.first_seen_at
    return now_str


def _handle_empty(
    candidate: discovery.Candidate, prior: RecordingState | None, now_str: str
) -> RecordingState:
    confirmed = (
        prior is not None
        and prior.status == RecordingStatus.PENDING
        and prior.source_size == candidate.size
        and prior.source_mtime == candidate.mtime
    )
    status = RecordingStatus.SKIPPED_EMPTY if confirmed else RecordingStatus.PENDING
    return RecordingState(
        status=status,
        source_filename=candidate.path.name,
        last_scanned_at=now_str,
        source_size=candidate.size,
        source_mtime=candidate.mtime,
        first_seen_at=_first_seen(prior, now_str),
        last_error_category=ErrorCategory.TRANSCRIPT_EMPTY.value,
    )


def _transient_failure(
    candidate: discovery.Candidate,
    prior: RecordingState | None,
    *,
    base_attempt_count: int,
    category: ErrorCategory,
    now_dt: datetime,
    now_str: str,
) -> RecordingState:
    attempt_count = base_attempt_count + 1
    common = {
        "source_filename": candidate.path.name,
        "last_scanned_at": now_str,
        "source_size": candidate.size,
        "source_mtime": candidate.mtime,
        "first_seen_at": _first_seen(prior, now_str),
        "last_error_category": category.value,
    }
    if attempt_count > len(RETRY_DELAYS):
        return RecordingState(
            status=RecordingStatus.NEEDS_ATTENTION,
            retry_count=attempt_count - 1,
            next_retry_at=None,
            **common,
        )
    next_retry_at = format_utc_iso(now_dt + RETRY_DELAYS[attempt_count - 1])
    return RecordingState(
        status=RecordingStatus.FAILED,
        retry_count=attempt_count,
        next_retry_at=next_retry_at,
        **common,
    )


def _attempt_extraction_and_archive(
    candidate: discovery.Candidate,
    prior: RecordingState | None,
    *,
    base_attempt_count: int,
    archive_root: Path,
    now_dt: datetime,
    now_str: str,
) -> RecordingState:
    result = extraction.extract_transcript(candidate.path)

    if result.status == extraction.ExtractionStatus.OK:
        recorded_at = attach_local_timezone(datetime.fromisoformat(candidate.recorded_at_iso))
        metadata = {
            "recording_id": candidate.recording_id,
            "source_filename": candidate.path.name,
            "source_format": candidate.source_format,
            "source_size": candidate.size,
            "source_mtime": candidate.mtime,
            "recorded_at": recorded_at.isoformat(),
            "locale": result.locale,
            "extraction_format_version": result.extraction_format_version,
            "archived_at": format_utc_iso(now_dt),
        }
        try:
            archive.write_archive_entry(archive_root, metadata, result.transcript_text)
        except ArchiveError as exc:
            if exc.category == ErrorCategory.ARCHIVE_CONFLICT:
                return RecordingState(
                    status=RecordingStatus.CONFLICT,
                    source_filename=candidate.path.name,
                    last_scanned_at=now_str,
                    source_size=candidate.size,
                    source_mtime=candidate.mtime,
                    first_seen_at=_first_seen(prior, now_str),
                    last_error_category=exc.category.value,
                )
            return _transient_failure(
                candidate,
                prior,
                base_attempt_count=base_attempt_count,
                category=exc.category,
                now_dt=now_dt,
                now_str=now_str,
            )
        return RecordingState(
            status=RecordingStatus.PROCESSED,
            source_filename=candidate.path.name,
            last_scanned_at=now_str,
            source_size=candidate.size,
            source_mtime=candidate.mtime,
            first_seen_at=_first_seen(prior, now_str),
        )

    if result.status == extraction.ExtractionStatus.EMPTY:
        return _handle_empty(candidate, prior, now_str)

    if result.status in (
        extraction.ExtractionStatus.ABSENT,
        extraction.ExtractionStatus.UNSUPPORTED,
    ):
        category = (
            ErrorCategory.TRANSCRIPT_ABSENT
            if result.status == extraction.ExtractionStatus.ABSENT
            else ErrorCategory.SOURCE_UNSUPPORTED
        )
        return RecordingState(
            status=RecordingStatus.SKIPPED_NO_TRANSCRIPT,
            source_filename=candidate.path.name,
            last_scanned_at=now_str,
            source_size=candidate.size,
            source_mtime=candidate.mtime,
            first_seen_at=_first_seen(prior, now_str),
            last_error_category=category.value,
        )

    return _transient_failure(
        candidate,
        prior,
        base_attempt_count=base_attempt_count,
        category=_EXTRACTION_FAILURE_CATEGORY[result.status],
        now_dt=now_dt,
        now_str=now_str,
    )


def _handle_candidate(
    candidate: discovery.Candidate,
    prior: RecordingState | None,
    *,
    archive_root: Path,
    now_dt: datetime,
    now_str: str,
) -> RecordingState | None:
    """Return the new `RecordingState` for one candidate, or None to leave it untouched."""
    if candidate.status == discovery.CandidateStatus.UNCHANGED and prior is not None:
        if prior.status in _STABLE_UNCHANGED_STATUSES:
            return None
        if prior.status == RecordingStatus.FAILED:
            if prior.next_retry_at is not None and now_str < prior.next_retry_at:
                return None  # not due yet
            return _attempt_extraction_and_archive(
                candidate,
                prior,
                base_attempt_count=prior.retry_count,
                archive_root=archive_root,
                now_dt=now_dt,
                now_str=now_str,
            )
        # PENDING (awaiting empty-reconfirmation, or a fresh manual-retry
        # reset): always re-attempt immediately, no backoff.
        return _attempt_extraction_and_archive(
            candidate,
            prior,
            base_attempt_count=0,
            archive_root=archive_root,
            now_dt=now_dt,
            now_str=now_str,
        )

    if candidate.status == discovery.CandidateStatus.DUPLICATE_ID:
        return RecordingState(
            status=RecordingStatus.CONFLICT,
            source_filename=candidate.path.name,
            last_scanned_at=now_str,
            source_size=candidate.size,
            source_mtime=candidate.mtime,
            first_seen_at=_first_seen(prior, now_str),
            last_error_category=ErrorCategory.ARCHIVE_CONFLICT.value,
        )

    if candidate.status == discovery.CandidateStatus.INACCESSIBLE:
        return _transient_failure(
            candidate,
            prior,
            base_attempt_count=0,
            category=ErrorCategory.SOURCE_INACCESSIBLE,
            now_dt=now_dt,
            now_str=now_str,
        )

    if candidate.status == discovery.CandidateStatus.UNSTABLE:
        return _transient_failure(
            candidate,
            prior,
            base_attempt_count=0,
            category=ErrorCategory.SOURCE_UNSTABLE,
            now_dt=now_dt,
            now_str=now_str,
        )

    # NEW or CHANGED: a fresh or changed source always gets a fresh attempt
    # cycle, regardless of whatever the prior record's status/backoff was —
    # this is the "source-file change reopens it" rule.
    return _attempt_extraction_and_archive(
        candidate,
        prior,
        base_attempt_count=0,
        archive_root=archive_root,
        now_dt=now_dt,
        now_str=now_str,
    )


def run_scan(
    config_path: Path,
    state_path: Path,
    *,
    now: Callable[[], datetime] | None = None,
) -> ScanSummary:
    """Run one scan: discover, extract, archive, and persist the outcome.

    `now` is an injectable clock (defaults to the real local time) so retry
    spacing can be tested deterministically without sleeping.
    """
    clock = now or (lambda: datetime.now().astimezone())
    cfg = config.load_config(config_path)
    recordings_source = Path(cfg.recordings_source).expanduser()
    archive_root = Path(cfg.archive_root).expanduser()
    lock_path = state_path.parent / "scan.lock"

    with ScanLock(lock_path):
        try:
            current_state = load_state(state_path)
        except StateError:
            # Corrupt/unreadable state.json: recover whatever the archive
            # itself can attest to rather than starting completely blind.
            current_state = reconcile_with_archive(State(), archive_root)

        started_at = format_utc_iso(clock())
        candidates = discovery.scan(recordings_source, current_state.recordings)

        recordings = dict(current_state.recordings)
        unidentified: list[UnidentifiedEntry] = []
        result_counts: dict[str, int] = {}
        last_error: str | None = None

        for candidate in candidates:
            if candidate.recording_id is None:
                unidentified.append(
                    UnidentifiedEntry(
                        path=redact_home_path(candidate.path), status=candidate.status.value
                    )
                )
                continue

            now_dt = clock()
            now_str = format_utc_iso(now_dt)
            prior = recordings.get(candidate.recording_id)
            new_record = _handle_candidate(
                candidate, prior, archive_root=archive_root, now_dt=now_dt, now_str=now_str
            )
            if new_record is None:
                new_record = prior
            recordings[candidate.recording_id] = new_record

            result_counts[new_record.status.value] = (
                result_counts.get(new_record.status.value, 0) + 1
            )
            if new_record.last_error_category:
                last_error = new_record.last_error_category

        final_state = State(
            schema_version=current_state.schema_version,
            recordings=recordings,
            last_scan_started_at=started_at,
            last_scan_completed_at=format_utc_iso(clock()),
            last_scan_result_counts=result_counts,
            last_scan_last_error=last_error,
        )
        save_state(state_path, final_state)

    return ScanSummary(
        result_counts=result_counts,
        unidentified=tuple(unidentified),
        last_error_category=last_error,
    )


def acknowledge(state: State, recording_id: str) -> State:
    """Mark a `needs_attention` record acknowledged, suppressing further auto-retry.

    The record's facts (retry count, last error category, fingerprint) are
    kept exactly as they were — acknowledgment changes visibility, not the
    underlying fact. Raises ValueError if there's no such record or it
    isn't in an acknowledgeable status.
    """
    record = state.recordings.get(recording_id)
    if record is None or record.status not in _ACKNOWLEDGEABLE:
        raise ValueError(f"{recording_id!r} has no needs_attention record to acknowledge")
    updated = dataclasses.replace(record, status=RecordingStatus.ACKNOWLEDGED)
    return dataclasses.replace(state, recordings={**state.recordings, recording_id: updated})


def retry(state: State, recording_id: str) -> State:
    """Reset one record to `pending` so the next scan attempts it immediately.

    Valid from `failed`, `needs_attention`, or `conflict` — retrying a
    `processed`/`skipped_*` record makes no sense (nothing failed), and
    `pending`/`acknowledged` are reached through their own flows.
    """
    record = state.recordings.get(recording_id)
    if record is None or record.status not in _RETRYABLE:
        raise ValueError(f"{recording_id!r} is not in a retryable status")
    updated = dataclasses.replace(
        record,
        status=RecordingStatus.PENDING,
        retry_count=0,
        next_retry_at=None,
        last_error_category=None,
    )
    return dataclasses.replace(state, recordings={**state.recordings, recording_id: updated})


def retry_all_needing_attention(state: State) -> State:
    """Bulk retry: reset every `needs_attention` record to `pending`."""
    updated_state = state
    for recording_id, record in state.recordings.items():
        if record.status == RecordingStatus.NEEDS_ATTENTION:
            updated_state = retry(updated_state, recording_id)
    return updated_state


def reconcile_with_archive(state: State, archive_root: Path) -> State:
    """Rebuild `processed` records from the archive tree, preserving everything else.

    Everything the archive can attest to (a completed entry) overwrites
    whatever `state.json` had for that ID — the archive is authoritative
    for success. Every other record (pending/failed/needs_attention/
    acknowledged/conflict, none of which has a completed archive file by
    definition) is left exactly as `state` already had it. `config.json`
    is a separate file this function never touches, so user settings are
    never at risk here regardless of what state.json looked like.
    """
    rebuilt = archive.rebuild_state_from_archive(archive_root)
    recordings = dict(state.recordings)
    for recording_id, rebuilt_record in rebuilt.items():
        prior = recordings.get(recording_id)
        recordings[recording_id] = dataclasses.replace(
            rebuilt_record,
            first_seen_at=prior.first_seen_at if prior is not None else None,
            last_scanned_at=prior.last_scanned_at if prior is not None else None,
        )
    return dataclasses.replace(state, recordings=recordings)
