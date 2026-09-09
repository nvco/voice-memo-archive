"""`state.json`: versioned operational state, retry tracking, and scan history.

Per AGENTS.md, this is rebuildable bookkeeping, not the archive's source of
truth — a missing or corrupted `state.json` must be recoverable rather than
fatal. `RecordingStatus` and the retry/scan-auditing fields below are
Phase 6's vocabulary (`tasks/030-...md`); Phase 2/3 had left `status` an
unconstrained string and this schema without them.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ErrorCategory, StateError
from .io_utils import atomic_write
from .paths import redact_home_path
from .schema import MigrationFn, migrate

CURRENT_SCHEMA_VERSION = 1

# No migrations exist yet — schema_version has always been 1. Registered
# here so a future bump has a tested chain to join (see schema.py).
_MIGRATIONS: dict[int, MigrationFn] = {}


class RecordingStatus(StrEnum):
    """Per-recording status vocabulary, per `tasks/000-initial-build.md` Phase 6.

    `PENDING` covers two distinct "not yet finalized" situations, both
    handled by `scheduling.py`: a source whose extracted transcript came
    back empty once and is awaiting a second, confirming scan before
    `SKIPPED_EMPTY` is finalized (the roadmap's "require stability across
    scans" rule), and a record a user has just reset via manual retry.
    Neither needs its own status — both simply mean "attempt again on the
    next eligible scan."
    """

    PENDING = "pending"
    PROCESSED = "processed"
    SKIPPED_EMPTY = "skipped_empty"
    SKIPPED_NO_TRANSCRIPT = "skipped_no_transcript"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"
    ACKNOWLEDGED = "acknowledged"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class RecordingState:
    status: RecordingStatus
    # The recording's own filename (not a full path) — kept here so a
    # `needs_attention`/`conflict` record is self-describing without
    # needing to re-run discovery to say which file it's about.
    source_filename: str | None = None
    last_scanned_at: str | None = None  # ISO 8601, UTC
    # Number of extraction/archive attempts made against the *current*
    # source fingerprint since the last success — reset to 0 whenever the
    # source changes or a manual retry resets the record. Only meaningful
    # for FAILED (drives retry spacing/exhaustion into NEEDS_ATTENTION);
    # unused (left 0) for every other status.
    retry_count: int = 0
    # Set only while status is FAILED, to gate the next automatic retry
    # attempt (`scheduling.RETRY_DELAYS`). None otherwise.
    next_retry_at: str | None = None  # ISO 8601, UTC
    last_error_category: str | None = None
    # Cheap source fingerprint (Phase 3 discovery), used to tell an
    # unchanged source file from one that changed since it was last seen —
    # normal scans skip reopening a file whose fingerprint still matches.
    source_size: int | None = None
    source_mtime: float | None = None
    # Set once, the first time discovery ever observes this recording ID —
    # never updated afterward. The mechanism a later "new since setup"
    # import mode (Phase 7) computes a cutoff against.
    first_seen_at: str | None = None  # ISO 8601, UTC

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordingState:
        return cls(
            status=RecordingStatus(data["status"]),
            source_filename=data.get("source_filename"),
            last_scanned_at=data.get("last_scanned_at"),
            retry_count=data.get("retry_count", 0),
            next_retry_at=data.get("next_retry_at"),
            last_error_category=data.get("last_error_category"),
            source_size=data.get("source_size"),
            source_mtime=data.get("source_mtime"),
            first_seen_at=data.get("first_seen_at"),
        )


@dataclass(frozen=True)
class State:
    schema_version: int = CURRENT_SCHEMA_VERSION
    recordings: dict[str, RecordingState] = field(default_factory=dict)
    last_scan_started_at: str | None = None
    last_scan_completed_at: str | None = None
    # Per-status counts from the most recently completed scan (e.g.
    # {"processed": 3, "failed": 1}) and the most recent factual,
    # transcript-free error category seen during it — the scan-level
    # auditing Phase 6 requires alongside the per-recording records above.
    last_scan_result_counts: dict[str, int] = field(default_factory=dict)
    last_scan_last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recordings": {rid: rs.to_dict() for rid, rs in self.recordings.items()},
            "last_scan_started_at": self.last_scan_started_at,
            "last_scan_completed_at": self.last_scan_completed_at,
            "last_scan_result_counts": self.last_scan_result_counts,
            "last_scan_last_error": self.last_scan_last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> State:
        try:
            migrated = migrate(data, current_version=CURRENT_SCHEMA_VERSION, migrations=_MIGRATIONS)
            recordings = {
                rid: RecordingState.from_dict(rs)
                for rid, rs in migrated.get("recordings", {}).items()
            }
            return cls(
                schema_version=migrated["schema_version"],
                recordings=recordings,
                last_scan_started_at=migrated.get("last_scan_started_at"),
                last_scan_completed_at=migrated.get("last_scan_completed_at"),
                last_scan_result_counts=migrated.get("last_scan_result_counts", {}),
                last_scan_last_error=migrated.get("last_scan_last_error"),
            )
        except (KeyError, ValueError) as exc:
            raise StateError(ErrorCategory.STATE_INVALID, str(exc)) from exc


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(
            ErrorCategory.STATE_INVALID,
            "state.json could not be read or parsed",
            detail={"path": redact_home_path(path)},
        ) from exc
    if not isinstance(raw, dict):
        raise StateError(
            ErrorCategory.STATE_INVALID,
            "state.json did not contain a JSON object",
            detail={"path": redact_home_path(path)},
        )
    return State.from_dict(raw)


def save_state(path: Path, state: State) -> None:
    atomic_write(path, json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")
