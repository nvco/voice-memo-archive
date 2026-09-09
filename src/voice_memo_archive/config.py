"""`config.json`: versioned user settings.

Per AGENTS.md, `config.json` holds user settings (as opposed to `state.py`'s
operational/retry data). A missing file is not an error — it means defaults,
so settings survive a state reset or a fresh checkout.

`import_mode`/`import_since`/`setup_completed_at`/`schedule_mode`/
`scan_interval_seconds` were added in Phase 7 (`tasks/035-...md`) for the
setup flow and `launchd` automation. They use `.get()` with defaults in
`from_dict` rather than the bracket-required style `recordings_source`/
`archive_root` use, so a `config.json` written before this phase (with
neither field present) keeps loading without a schema migration — no
migration exists yet, and Phase 3's precedent (`state.py`'s
`source_size`/`source_mtime`) was to prefer optional-with-default over a
migration when nothing has shipped against the field's absence yet.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .errors import ConfigError, ErrorCategory
from .io_utils import atomic_write
from .paths import redact_home_path
from .schema import MigrationFn, migrate

CURRENT_SCHEMA_VERSION = 1

# Confirmed by real-sample inspection in
# tasks/005-platform-feasibility-and-data-contract.md.
DEFAULT_RECORDINGS_SOURCE = (
    "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
)
# Recorded in tasks/000-initial-build.md's Plan history.
DEFAULT_ARCHIVE_ROOT = "~/Documents/Voice Memo Archive"

# "all": every existing recording. "new_only": nothing existing at setup
# time, only recordings whose own recorded_at falls on/after the local
# calendar day setup completed. "date": recordings whose recorded_at is
# on/after `import_since`. See scheduling.py's import-cutoff filter.
IMPORT_MODES = frozenset({"all", "new_only", "date"})
DEFAULT_IMPORT_MODE = "all"

# "monitoring": a launchd WatchPaths trigger on the recordings folder, plus
# the periodic StartInterval scan as the roadmap's "reliable fallback to
# folder events". "scheduled": StartInterval only, no WatchPaths.
SCHEDULE_MODES = frozenset({"monitoring", "scheduled"})
DEFAULT_SCHEDULE_MODE = "monitoring"

# The fixed menu setup offers, per the roadmap's "supported scan
# intervals" — not enforced by `Config` itself (a hand-edited config.json
# with a different positive interval still loads), just the choices the
# `setup` command presents.
SUPPORTED_SCAN_INTERVALS_SECONDS = (300, 900, 1800, 3600, 21600)  # 5m/15m/30m/1h/6h
DEFAULT_SCAN_INTERVAL_SECONDS = 900

# No migrations exist yet — schema_version has always been 1. Registered
# here so a future bump has a tested chain to join (see schema.py).
_MIGRATIONS: dict[int, MigrationFn] = {}


@dataclass(frozen=True)
class Config:
    schema_version: int = CURRENT_SCHEMA_VERSION
    recordings_source: str = DEFAULT_RECORDINGS_SOURCE
    archive_root: str = DEFAULT_ARCHIVE_ROOT
    import_mode: str = DEFAULT_IMPORT_MODE
    import_since: str | None = None  # "YYYY-MM-DD", only meaningful when import_mode == "date"
    # Set once, when `setup` completes — the cutoff `import_mode ==
    # "new_only"` filters against. UTC ISO 8601, via paths.format_utc_iso.
    setup_completed_at: str | None = None
    schedule_mode: str = DEFAULT_SCHEDULE_MODE
    scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        try:
            migrated = migrate(data, current_version=CURRENT_SCHEMA_VERSION, migrations=_MIGRATIONS)
            import_mode = migrated.get("import_mode", DEFAULT_IMPORT_MODE)
            if import_mode not in IMPORT_MODES:
                raise ValueError(f"unknown import_mode: {import_mode!r}")
            schedule_mode = migrated.get("schedule_mode", DEFAULT_SCHEDULE_MODE)
            if schedule_mode not in SCHEDULE_MODES:
                raise ValueError(f"unknown schedule_mode: {schedule_mode!r}")
            scan_interval_seconds = migrated.get(
                "scan_interval_seconds", DEFAULT_SCAN_INTERVAL_SECONDS
            )
            if not isinstance(scan_interval_seconds, int) or scan_interval_seconds <= 0:
                raise ValueError(
                    f"scan_interval_seconds must be a positive int: {scan_interval_seconds!r}"
                )
            import_since = migrated.get("import_since")
            if import_since is not None:
                # Validated here, not just left to whatever later reads it
                # (scheduling.import_cutoff_date) — a malformed date must
                # fail loudly at load time as a ConfigError, not crash a
                # scan later with a bare, un-wrapped ValueError.
                date.fromisoformat(import_since)
            setup_completed_at = migrated.get("setup_completed_at")
            if setup_completed_at is not None:
                datetime.fromisoformat(setup_completed_at)
            return cls(
                schema_version=migrated["schema_version"],
                recordings_source=migrated["recordings_source"],
                archive_root=migrated["archive_root"],
                import_mode=import_mode,
                import_since=import_since,
                setup_completed_at=setup_completed_at,
                schedule_mode=schedule_mode,
                scan_interval_seconds=scan_interval_seconds,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ConfigError(ErrorCategory.CONFIG_INVALID, str(exc)) from exc


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(
            ErrorCategory.CONFIG_INVALID,
            "config.json could not be read or parsed",
            detail={"path": redact_home_path(path)},
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(
            ErrorCategory.CONFIG_INVALID,
            "config.json did not contain a JSON object",
            detail={"path": redact_home_path(path)},
        )
    return Config.from_dict(raw)


def save_config(path: Path, config: Config) -> None:
    atomic_write(path, json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n")
