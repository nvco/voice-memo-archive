"""File discovery and source metadata. Owned by Phase 3.

Enumerates the configured recordings folder, applies the exclusion list
from tasks/005-...md's Findings (`*.waveform`, `*.composition/`, `Capture/`,
`CaptureRecovery/`, `.CloudRecordings_SUPPORT/`, `CloudRecordings_ckAssets/`,
`CloudRecordings.db*`), and resolves each candidate's dedup ID (including
the composition-sidecar case for ID-less filenames).
"""

from __future__ import annotations

from pathlib import Path


def scan(recordings_source: Path) -> None:
    raise NotImplementedError("file discovery is implemented in Phase 3")
