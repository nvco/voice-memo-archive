"""First-run setup flow (Phase 7).

Two-step by design, so the CLI can show a preview and let the user cancel
before anything is written: `build_setup_plan` validates the chosen options
and computes what the initial import would consider, with no side effects
at all; `commit_setup` is the only function that writes `config.json`.

Setup never touches `state.json` or the archive tree — a re-run simply
overwrites `config.json` with the new choices (including a fresh
`setup_completed_at`), which is safe and idempotent because `config.json`
is a complete settings record, not something merged with prior state.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from . import config, discovery, scheduling
from .paths import format_utc_iso


@dataclasses.dataclass(frozen=True)
class SetupPlan:
    recordings_source: str
    archive_root: str
    import_mode: str
    import_since: str | None
    schedule_mode: str
    scan_interval_seconds: int
    candidate_preview_count: int
    # True if archive_root resolves under ~/Documents, which macOS *may*
    # sync via iCloud Drive depending on the user's own System Settings —
    # a disclosure, not a claim about the user's actual settings.
    archive_root_may_sync: bool
    # None until `commit_setup` actually writes config.json.
    setup_completed_at: str | None = None


def may_be_icloud_synced(path: str | Path) -> bool:
    documents = (Path.home() / "Documents").resolve()
    try:
        Path(path).expanduser().resolve().relative_to(documents)
        return True
    except ValueError:
        return False


def preview_candidate_count(
    recordings_source: Path, *, import_mode: str, import_since: str | None
) -> int:
    """How many recordings the initial import would actually consider.

    "new_only" is always 0 here — by definition nothing existing yet
    counts as new; only recordings that appear after setup completes will.
    This is the honest answer, not an approximation of it.
    """
    if import_mode == "new_only":
        return 0
    cutoff = None
    if import_mode == "date" and import_since:
        cutoff = date.fromisoformat(import_since)
    candidates = discovery.scan(recordings_source, {})
    return sum(
        1
        for candidate in candidates
        if candidate.recording_id is not None and scheduling.passes_import_cutoff(candidate, cutoff)
    )


def build_setup_plan(
    *,
    recordings_source: str | None = None,
    archive_root: str | None = None,
    import_mode: str = config.DEFAULT_IMPORT_MODE,
    import_since: str | None = None,
    schedule_mode: str = config.DEFAULT_SCHEDULE_MODE,
    scan_interval_seconds: int = config.DEFAULT_SCAN_INTERVAL_SECONDS,
) -> SetupPlan:
    """Validate the chosen options and preview the initial import. No side effects."""
    if import_mode not in config.IMPORT_MODES:
        raise ValueError(f"unknown import_mode: {import_mode!r}")
    if import_mode == "date" and not import_since:
        raise ValueError("import_since is required when import_mode is 'date'")
    if schedule_mode not in config.SCHEDULE_MODES:
        raise ValueError(f"unknown schedule_mode: {schedule_mode!r}")
    if scan_interval_seconds <= 0:
        raise ValueError("scan_interval_seconds must be positive")

    resolved_recordings_source = recordings_source or config.DEFAULT_RECORDINGS_SOURCE
    resolved_archive_root = archive_root or config.DEFAULT_ARCHIVE_ROOT

    candidate_count = preview_candidate_count(
        Path(resolved_recordings_source).expanduser(),
        import_mode=import_mode,
        import_since=import_since,
    )

    return SetupPlan(
        recordings_source=resolved_recordings_source,
        archive_root=resolved_archive_root,
        import_mode=import_mode,
        import_since=import_since,
        schedule_mode=schedule_mode,
        scan_interval_seconds=scan_interval_seconds,
        candidate_preview_count=candidate_count,
        archive_root_may_sync=may_be_icloud_synced(resolved_archive_root),
    )


def commit_setup(
    config_path: Path,
    plan: SetupPlan,
    *,
    now: Callable[[], datetime] | None = None,
) -> SetupPlan:
    """Write `config.json` from an already-built, already-shown plan."""
    clock = now or (lambda: datetime.now().astimezone())
    completed_at = format_utc_iso(clock())
    new_config = config.Config(
        recordings_source=plan.recordings_source,
        archive_root=plan.archive_root,
        import_mode=plan.import_mode,
        import_since=plan.import_since,
        setup_completed_at=completed_at,
        schedule_mode=plan.schedule_mode,
        scan_interval_seconds=plan.scan_interval_seconds,
    )
    config.save_config(config_path, new_config)
    return dataclasses.replace(plan, setup_completed_at=completed_at)
