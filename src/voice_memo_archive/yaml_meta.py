"""Versioned schema for the YAML frontmatter written into each archive file.

Per AGENTS.md: "Keep generated YAML metadata factual. Do not add
AI-generated summaries, titles, tags, or interpretations to the source
archive." `REQUIRED_FIELDS` is the complete factual field set — Phase 5
(archive output) is what actually assembles a Markdown file around this;
this module only owns the metadata shape and its serialization.

`source_filename`, `source_size`, `source_mtime`, and `transcript_sha256`
were added in Phase 5 to satisfy `tasks/000-initial-build.md` Phase 5's
"Include the original source filename..." requirement and its "Archive
metadata can rebuild successful operational state" exit criterion — the
frontmatter must carry enough facts on its own to reconstruct
`state.RecordingState`'s fingerprint and to detect a changed source or
changed transcript without needing `state.json`. The initial Phase 2 draft
of this schema had only the fields Phase 1/2 already had in hand
(`recording_id`, `source_format`, `recorded_at`, `locale`,
`extraction_format_version`, `archived_at`); it omitted these because
Phase 5's own scope wasn't drafted yet (see `tasks/025-...md`'s
Deviations). `transcript_sha256` is always computed by
`archive.write_archive_entry` from the transcript text actually being
written, never supplied independently by a caller — see that module.
"""

from __future__ import annotations

from typing import Any

import yaml

CURRENT_SCHEMA_VERSION = 1

# Every field here must be a plain fact recorded about the source recording
# or the extraction that produced this archive entry — never an
# interpretation. See tasks/005-...md's "Draft extraction result contract"
# for where these values come from.
REQUIRED_FIELDS = frozenset(
    {
        "recording_id",
        "source_filename",
        "source_format",
        "source_size",
        "source_mtime",
        "recorded_at",
        "locale",
        "extraction_format_version",
        "transcript_sha256",
        "archived_at",
    }
)


def validate_metadata(fields: dict[str, Any]) -> None:
    """Raise ValueError unless `fields` has exactly `REQUIRED_FIELDS`.

    Shared by `dump_metadata` (writing) and archive inspection (reading) so
    both directions reject the same schema drift, rather than a read path
    silently accepting a payload the write path would never have produced.
    """
    missing = REQUIRED_FIELDS - fields.keys()
    if missing:
        raise ValueError(f"missing required metadata field(s): {sorted(missing)}")
    unknown = fields.keys() - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"unknown metadata field(s): {sorted(unknown)}")


def dump_metadata(fields: dict[str, Any]) -> str:
    """Serialize a factual metadata dict to YAML frontmatter text.

    Raises ValueError if a required field is missing or an unknown field is
    present, so a caller can't silently drift the archive's schema.
    """
    validate_metadata(fields)
    ordered = {key: fields[key] for key in sorted(REQUIRED_FIELDS)}
    return yaml.safe_dump(ordered, sort_keys=True, allow_unicode=True)


def load_metadata(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter did not parse to a mapping")
    return data
