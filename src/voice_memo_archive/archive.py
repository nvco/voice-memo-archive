"""Archive output, deduplication, and conflicts. Owned by Phase 5.

Writes the year/month/day-grouped Markdown archive files (YAML frontmatter
via `yaml_meta` plus the transcript body), using `io_utils.atomic_write` so
an interrupted write can never produce a completed-looking partial archive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_archive_entry(archive_root: Path, metadata: dict[str, Any], transcript_text: str) -> None:
    raise NotImplementedError("archive output is implemented in Phase 5")
