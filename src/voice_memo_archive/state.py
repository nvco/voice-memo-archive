"""`state.json`: versioned operational state, retry tracking, and scan history.

Per AGENTS.md, this is rebuildable bookkeeping, not the archive's source of
truth — a missing or corrupted `state.json` must be recoverable rather than
fatal. The per-recording status vocabulary and full retry policy belong to
Phase 6; this establishes the versioned envelope and record shape they'll
extend.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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


@dataclass(frozen=True)
class RecordingState:
    status: str
    last_scanned_at: str | None = None  # ISO 8601, UTC
    retry_count: int = 0
    last_error_category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordingState:
        return cls(
            status=data["status"],
            last_scanned_at=data.get("last_scanned_at"),
            retry_count=data.get("retry_count", 0),
            last_error_category=data.get("last_error_category"),
        )


@dataclass(frozen=True)
class State:
    schema_version: int = CURRENT_SCHEMA_VERSION
    recordings: dict[str, RecordingState] = field(default_factory=dict)
    last_scan_started_at: str | None = None
    last_scan_completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recordings": {rid: rs.to_dict() for rid, rs in self.recordings.items()},
            "last_scan_started_at": self.last_scan_started_at,
            "last_scan_completed_at": self.last_scan_completed_at,
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
