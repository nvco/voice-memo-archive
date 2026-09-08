"""Versioned schema for the YAML frontmatter written into each archive file.

Per AGENTS.md: "Keep generated YAML metadata factual. Do not add
AI-generated summaries, titles, tags, or interpretations to the source
archive." `REQUIRED_FIELDS` is the complete factual field set — Phase 5
(archive output) is what actually assembles a Markdown file around this;
this module only owns the metadata shape and its serialization.
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
        "source_format",
        "recorded_at",
        "locale",
        "extraction_format_version",
        "archived_at",
    }
)


def dump_metadata(fields: dict[str, Any]) -> str:
    """Serialize a factual metadata dict to YAML frontmatter text.

    Raises ValueError if a required field is missing or an unknown field is
    present, so a caller can't silently drift the archive's schema.
    """
    missing = REQUIRED_FIELDS - fields.keys()
    if missing:
        raise ValueError(f"missing required metadata field(s): {sorted(missing)}")
    unknown = fields.keys() - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"unknown metadata field(s): {sorted(unknown)}")

    ordered = {key: fields[key] for key in sorted(REQUIRED_FIELDS)}
    return yaml.safe_dump(ordered, sort_keys=True, allow_unicode=True)


def load_metadata(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter did not parse to a mapping")
    return data
