"""Archive output, deduplication, and conflicts (Phase 5).

Writes the year/month/day-grouped Markdown archive files (YAML frontmatter
via `yaml_meta` plus the transcript body), using `io_utils.atomic_write` so
an interrupted write can never produce a completed-looking partial archive.

Layout: `<archive_root>/<YYYY>/<MM>/<DD>/<HHMMSS>-<recording_id>.md`, derived
entirely from `metadata["recorded_at"]` and `metadata["recording_id"]` — the
same two source facts discovery already treats as identity, never from
transcript content. `archive_root` is expected already resolved (e.g.
`Path(config.archive_root).expanduser()`); this module does not read
`config.py` itself.

Conflict policy: a completed archive file is never overwritten, and
`scan`/`write_archive_entry` never delete one either. If a write is
requested for a path that already holds a different source filename,
source fingerprint, or transcript, `write_archive_entry` raises
`ArchiveError(ErrorCategory.ARCHIVE_CONFLICT, ...)` instead — the existing
file is left exactly as it was, so historical text is always preserved. A
write that exactly matches what's already on disk is a silent no-op.

`empty_archive` is the one deliberate exception: an explicit, separately
user-invoked deletion of every recognized archive entry (never a side
effect of scanning), added in
`tasks/051-empty-archive-command.md` once the archive stopped being
required to be a durable, permanent store for every user of this tool.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .errors import ArchiveError, ErrorCategory
from .io_utils import atomic_write
from .paths import archive_date_parts, redact_home_path
from .state import RecordingState, RecordingStatus
from .yaml_meta import dump_metadata, load_metadata, validate_metadata

_FRONTMATTER_DELIMITER = "---"

# A completed archive file only ever exists for a successfully extracted,
# non-empty transcript, so this is always the status a rebuilt-from-archive
# entry gets.
REBUILT_STATUS = RecordingStatus.PROCESSED


def _archive_path(archive_root: Path, metadata: dict[str, Any]) -> Path:
    recording_id = metadata["recording_id"]
    if not recording_id or "/" in recording_id or recording_id in {".", ".."}:
        raise ValueError(f"unsafe recording_id for an archive filename: {recording_id!r}")
    recorded_at = datetime.fromisoformat(metadata["recorded_at"])
    year, month, day = archive_date_parts(recorded_at)
    filename = f"{recorded_at.strftime('%H%M%S')}-{recording_id}.md"
    return archive_root / year / month / day / filename


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split archive file text into (frontmatter YAML, body).

    Only the *second* line that is exactly `---` ends the frontmatter block
    — anything the transcript body itself contains, including a bare `---`
    line, is never mistaken for a delimiter because it is never inspected
    again once the body starts.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != _FRONTMATTER_DELIMITER:
        raise ValueError("archive file is missing its frontmatter delimiter")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\n") == _FRONTMATTER_DELIMITER:
            frontmatter = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            return frontmatter, body.lstrip("\n")
    raise ValueError("archive file frontmatter is not terminated")


def read_archive_entry(path: Path) -> tuple[dict[str, Any], str]:
    """Parse a completed archive file into (metadata, transcript body).

    Raises ValueError if the frontmatter delimiters are missing/unterminated,
    the YAML doesn't parse to a mapping, or the field set doesn't match
    `yaml_meta.REQUIRED_FIELDS` exactly — callers (e.g. `inspect_archive`)
    treat any of these as a malformed entry, never a crash.
    """
    text = path.read_text(encoding="utf-8")
    frontmatter_text, body = _split_frontmatter(text)
    metadata = load_metadata(frontmatter_text)
    validate_metadata(metadata)
    return metadata, body


def _detect_conflict(existing: dict[str, Any], new: dict[str, Any]) -> str | None:
    if existing["source_filename"] != new["source_filename"]:
        return "duplicate memo ID: already archived from a different source filename"
    if (
        existing["source_size"] != new["source_size"]
        or existing["source_mtime"] != new["source_mtime"]
    ):
        return "changed source: source file fingerprint differs from the completed archive"
    if existing["transcript_sha256"] != new["transcript_sha256"]:
        return "changed transcript: extracted transcript differs from the completed archive"
    return None


def write_archive_entry(archive_root: Path, metadata: dict[str, Any], transcript_text: str) -> None:
    """Write one archive entry, or raise on an unresolved conflict.

    `metadata` must satisfy `yaml_meta.REQUIRED_FIELDS` except
    `transcript_sha256`, which this function computes itself from
    `transcript_text` and injects — a caller never supplies it directly, so
    the stored hash can never drift from the text actually written.

    Never overwrites or deletes an existing archive file. If one already
    exists at the deterministic path for this recording, it is left
    untouched: an exact match is a no-op, any difference raises
    `ArchiveError(ErrorCategory.ARCHIVE_CONFLICT, ...)` for the caller to
    surface as an actionable conflict.
    """
    full_metadata = dict(metadata)
    full_metadata["transcript_sha256"] = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
    frontmatter = dump_metadata(full_metadata)

    target = _archive_path(archive_root, full_metadata)
    if target.exists():
        existing_metadata, _existing_body = read_archive_entry(target)
        conflict = _detect_conflict(existing_metadata, full_metadata)
        if conflict is not None:
            raise ArchiveError(
                ErrorCategory.ARCHIVE_CONFLICT,
                conflict,
                detail={
                    "path": redact_home_path(target),
                    "recording_id": full_metadata["recording_id"],
                },
            )
        return

    # No trailing newline is appended after `transcript_text` even if it
    # lacks one: this is transcript content, and Phase 4's fidelity
    # invariant ("preserve meaningful whitespace") applies here too — the
    # body byte-for-byte is exactly what was extracted, never normalized
    # for file-convention neatness.
    content = (
        f"{_FRONTMATTER_DELIMITER}\n{frontmatter}{_FRONTMATTER_DELIMITER}\n\n{transcript_text}"
    )
    atomic_write(target, content)


@dataclass(frozen=True)
class ArchiveEntry:
    path: Path
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MalformedArchiveEntry:
    path: Path
    reason: str


@dataclass(frozen=True)
class ArchiveInspection:
    entries: tuple[ArchiveEntry, ...]
    malformed: tuple[MalformedArchiveEntry, ...]
    orphaned: tuple[Path, ...]


def inspect_archive(archive_root: Path) -> ArchiveInspection:
    """Walk the archive tree and classify every file found there.

    A `.md` file that fails to parse (missing/unterminated frontmatter,
    invalid YAML, or a field set that doesn't match the current schema) is
    reported as malformed rather than raising — a doctor/status command
    needs to enumerate every problem in one pass, not stop at the first.
    Anything that isn't a `.md` file at all (a stray temp file left behind
    by a killed process, e.g.) is reported as orphaned.
    """
    if not archive_root.exists():
        return ArchiveInspection(entries=(), malformed=(), orphaned=())

    entries: list[ArchiveEntry] = []
    malformed: list[MalformedArchiveEntry] = []
    orphaned: list[Path] = []
    for path in sorted(p for p in archive_root.rglob("*") if p.is_file()):
        if path.suffix != ".md":
            orphaned.append(path)
            continue
        try:
            metadata, _body = read_archive_entry(path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
            malformed.append(MalformedArchiveEntry(path=path, reason=str(exc)))
            continue
        entries.append(ArchiveEntry(path=path, metadata=metadata))
    return ArchiveInspection(
        entries=tuple(entries), malformed=tuple(malformed), orphaned=tuple(orphaned)
    )


@dataclass(frozen=True)
class EmptyResult:
    deleted_count: int
    left_count: int  # orphaned (non-`.md`) files found and deliberately left alone


def empty_archive(archive_root: Path) -> EmptyResult:
    """Delete every recognized archive entry — valid or malformed `.md`
    files alike — then remove any subdirectories left empty as a result.

    Deliberately narrow: only files `inspect_archive` already recognizes
    as belonging to this tool are ever removed. An orphaned (non-`.md`)
    file is left exactly where it is and counted, never guessed at or
    swept away — the same "never touch what it doesn't clearly own"
    discipline as every other command in this project. `config.json`/
    `state.json` are untouched; a recording already marked `processed`
    stays that way, so a normal `scan` afterward does not re-add it.
    """
    inspection = inspect_archive(archive_root)
    for entry in inspection.entries:
        entry.path.unlink()
    for malformed in inspection.malformed:
        malformed.path.unlink()

    # Deepest directories first, so a now-empty parent can be removed too.
    for directory in sorted(
        (p for p in archive_root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass  # not empty — an orphaned file (or a nested one) lives here

    return EmptyResult(
        deleted_count=len(inspection.entries) + len(inspection.malformed),
        left_count=len(inspection.orphaned),
    )


def rebuild_state_from_archive(archive_root: Path) -> dict[str, RecordingState]:
    """Reconstruct per-recording operational state from archive frontmatter alone.

    Only covers what a completed archive entry can attest to by itself
    (fingerprint at time of archiving); it deliberately never sets
    `first_seen_at` — that's the first time *discovery* saw the recording,
    which the archive has no record of, so a reconciliation caller should
    treat it as unknown rather than guessing `archived_at` as a substitute.
    Malformed and orphaned entries are the caller's concern
    (`inspect_archive`), not reflected here.
    """
    inspection = inspect_archive(archive_root)
    return {
        entry.metadata["recording_id"]: RecordingState(
            status=REBUILT_STATUS,
            source_filename=entry.metadata["source_filename"],
            source_size=entry.metadata["source_size"],
            source_mtime=entry.metadata["source_mtime"],
        )
        for entry in inspection.entries
    }
