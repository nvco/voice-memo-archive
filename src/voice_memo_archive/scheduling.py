"""Operational state, retries, and `launchd` automation. Owned by Phase 6/7.

Drives a scan under `io_utils.ScanLock`, decides retry spacing/exhaustion
from `state.RecordingState`, and is the target `launchd` invokes — the CLI
in `cli.py` is a thin caller of this, not a second copy of its logic.
"""

from __future__ import annotations

from pathlib import Path


def run_scan(config_path: Path, state_path: Path) -> None:
    raise NotImplementedError("scan orchestration is implemented in Phase 6/7")
