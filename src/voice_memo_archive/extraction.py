"""Native transcript extraction. Owned by Phase 4.

Implements the two container lookup paths confirmed in
tasks/005-platform-feasibility-and-data-contract.md: a direct
`moov/trak/udta/tsrp` box for `.m4a`, and a `moov/trak/meta` (no ISO
version/flags header) `keys`/`ilst` scan for the `com.apple.VoiceMemos.tsrp`
metadata key on `.qta`. Returns the extraction result shape drawn from that
file's "Draft extraction result contract" (`status`, `transcript_text`,
`timing`, `locale`, `extraction_format_version`).
"""

from __future__ import annotations

from pathlib import Path


def extract_transcript(recording_path: Path) -> None:
    raise NotImplementedError("native transcript extraction is implemented in Phase 4")
