"""Setup and `doctor`-style diagnostics. Owned by Phase 7/8.

Explicitly detects the Full-Disk-Access-denied case (`Operation not
permitted` on a folder read, confirmed in
tasks/005-platform-feasibility-and-data-contract.md's Findings — macOS
gives no programmatic prompt for this permission) and points the user to
System Settings, rather than reporting a generic "no recordings found."
"""

from __future__ import annotations

from pathlib import Path


def check_recordings_access(recordings_source: Path) -> None:
    raise NotImplementedError("doctor-style diagnostics are implemented in Phase 7/8")
