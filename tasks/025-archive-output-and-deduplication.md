# Archive output, deduplication, and conflicts

Focused task plan for Phase 5 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Confirmed `config.Config.archive_root` already exists (Phase 2), default
  `~/Documents/Voice Memo Archive`, matching the roadmap default exactly —
  archive output just consumes it, nothing to add there.
- Closed a real schema gap found while drafting this task file: the
  roadmap's Phase 5 scope requires frontmatter to include "the original
  source filename," but `yaml_meta.REQUIRED_FIELDS` (drafted in Phase 2)
  never had it. Added `source_filename`, plus `source_size`/`source_mtime`
  (the fingerprint fields needed for "changed source" detection and for
  rebuilding `state.RecordingState` from the archive alone) and
  `transcript_sha256` (for "changed transcript" detection without storing
  or diffing full transcript text). See Deviations below.
- Implemented `archive.write_archive_entry`: builds the deterministic
  `<archive_root>/<YYYY>/<MM>/<DD>/<HHMMSS>-<recording_id>.md` path from
  `metadata["recorded_at"]` + `metadata["recording_id"]` only (never from
  transcript content), assembles frontmatter via `yaml_meta.dump_metadata`,
  and writes via `io_utils.atomic_write`. Collision rule: since the
  filename is built directly from the recording's own (already-unique)
  `recording_id`, no two distinct recordings can ever target the same
  path — a same-path write always means "this is the same recording,"
  which is exactly what conflict detection below is for. A bare `.`/`..`
  or a `recording_id` containing `/` is rejected outright rather than
  trusted into a path.
- `transcript_sha256` is always computed by `write_archive_entry` itself
  from the `transcript_text` argument and injected before validation — a
  caller cannot pass a stale or mismatched hash; the stored hash can never
  drift from the text actually written
  (`test_write_computes_transcript_hash_from_actual_text_not_caller_input`).
- Conflict detection implemented in `_detect_conflict`: comparing an
  existing archive's frontmatter against a new write request. Different
  `source_filename` -> "duplicate memo ID" (two distinct source files
  claiming the same recording ID); different `source_size`/`source_mtime`
  -> "changed source"; same fingerprint but different `transcript_sha256`
  -> "changed transcript". Any of the three raises
  `ArchiveError(ErrorCategory.ARCHIVE_CONFLICT, ...)` (that category
  already existed in `errors.py` from Phase 2) and leaves the existing
  file completely untouched — verified directly for all three cases. An
  exact-match rewrite is a silent no-op (idempotent), also tested.
  Phase 5 has no delete path anywhere in this module, satisfying "never
  delete an archive merely because its source later disappears" by
  construction rather than by a runtime check.
- Fixed a real fidelity bug caught by the boundary-case tests during
  implementation: the first draft of `write_archive_entry` appended a
  trailing `\n` to the file if `transcript_text` didn't already end in
  one, for file-convention neatness. That silently added a byte the
  extractor never produced, violating Phase 4's "preserve meaningful
  whitespace" invariant. Removed — the body is written byte-for-byte with
  no normalization.
- `read_archive_entry` / `_split_frontmatter` parse a completed archive
  file back into `(metadata, transcript_text)`. The frontmatter block ends
  at the *second* line that is exactly `---`; a transcript body containing
  its own `---` line (tested directly) is never mistaken for the
  delimiter because the parser stops looking once the body starts.
- `inspect_archive` walks the archive tree once and classifies every file:
  valid entries, malformed entries (unparseable frontmatter, or frontmatter
  that doesn't match `yaml_meta.REQUIRED_FIELDS` exactly — e.g. an older
  schema version's file, or a stray temp file), and orphaned files (anything
  without a `.md` extension, e.g. a leftover `.tmp` from a killed process).
  Reports every problem in one pass rather than raising at the first one.
- `rebuild_state_from_archive` reconstructs a `dict[recording_id,
  RecordingState]` from `inspect_archive`'s valid entries alone —
  `status="ok"`, `source_size`, `source_mtime` — satisfying "archive
  metadata can rebuild successful operational state." Deliberately leaves
  `first_seen_at` as `None`: that field means "the first time discovery
  ever observed this recording," which the archive itself has no record
  of, so reconciliation must treat it as unknown rather than guessing
  `archived_at` as a substitute.
- 20 new tests in `tests/test_archive.py` covering: path construction,
  metadata/body round-trip, hash-is-always-computed (not caller-supplied),
  five YAML/Markdown boundary cases (embedded `---` line, a body that is
  only `---`, Unicode, a trailing colon, an empty transcript), idempotent
  identical rewrite, all three conflict kinds (each verified to both raise
  `ARCHIVE_CONFLICT` and leave the original file's content unchanged),
  no leftover temp file after a normal write, rejection of an unsafe
  `recording_id`, and `inspect_archive`/`rebuild_state_from_archive`
  against missing-root, valid, malformed, incomplete-frontmatter, and
  orphaned-file cases. 101 tests total in the suite; `ruff check`/
  `ruff format --check` clean.

**Not done yet — next action:**

- No integration with `discovery.py`'s `Candidate` or `extraction.py`'s
  `ExtractionResult` yet — `write_archive_entry` takes a bare metadata
  dict and transcript text. Assembling that dict from a `Candidate` +
  `ExtractionResult` (and deciding exactly how `recorded_at`'s timezone
  offset gets attached — `paths.attach_local_timezone` already exists for
  this) is Phase 6's scan-orchestration job, per the same module-boundary
  precedent `tasks/015-...md` used for `first_seen_at`.
- The actual conflict *reporting* surface (what a user sees, how it gets
  acknowledged/retried) is Phase 6's "retries and recovery" job — Phase 5
  only guarantees the conflict is detected, raised with enough structured
  detail to act on, and never silently resolved by overwriting.
- "Allow the user to override [the archive root] during command-line
  setup" is a CLI/setup UX concern (`config.archive_root` is already
  mechanically overridable by editing `config.json`) — the actual
  interactive setup flow is Phase 7's job, consistent with how Phase 3
  deferred "import mode" UX to the same phase.
- None of this has been exercised against a real extracted transcript or
  real archive tree yet — only synthetic metadata/text in
  `tests/test_archive.py`. Real-sample verification is Phase 9's job.

## Scope and decisions to validate

- [x] Default the archive root to `~/Documents/Voice Memo Archive/`,
      overridable during command-line setup. _Already implemented in Phase 2
      as `config.Config.archive_root`; Phase 5 just consumes it. The
      interactive setup UX for overriding it is Phase 7's job — see "Not
      done yet" above._ Build the `YYYY/MM/DD/` directory layout and a
      deterministic Markdown filename from source facts (recorded
      timestamp + memo ID, not transcript content). _Implemented:
      `<archive_root>/<YYYY>/<MM>/<DD>/<HHMMSS>-<recording_id>.md`._
- [x] Write minimal factual YAML frontmatter that safely round-trips
      arbitrary Unicode and punctuation, including characters that could
      be misread as YAML/Markdown structure (leading `---`, unescaped
      colons, embedded newlines in a scalar). _`yaml_meta.dump_metadata`
      enforces the required/unknown field set; `archive.py` assembles the
      Markdown body around it; five boundary cases tested directly in
      `tests/test_archive.py`, including a transcript body containing its
      own `---` line._
- [x] Write to a temporary file on the destination filesystem and
      atomically rename it (`io_utils.atomic_write`) so normal processing
      never leaves partial output or overwrites a completed archive file
      in place. _`write_archive_entry` uses `atomic_write` for every new
      file, and never calls it at all when an existing file is detected
      (conflict-or-no-op path only) — so an existing completed archive is
      never even opened for writing._
- [x] Include the original source filename, recorded local time, memo ID,
      and source format in frontmatter. Keep metadata factual — no
      generated titles, summaries, tags, interpretations, or
      transcript-derived dedup key. _`yaml_meta.REQUIRED_FIELDS` now
      includes `source_filename`, `source_size`, `source_mtime`,
      `recording_id`, `source_format`, `recorded_at`, `locale`,
      `extraction_format_version`, `transcript_sha256`, `archived_at` —
      see Deviations below._
- [x] Compare later source fingerprints and extracted transcript hashes
      against a completed archive's frontmatter. Treat changed transcript,
      changed source, and duplicate memo ID as visible, reported
      conflicts — not silent overwrites and not crashes. _Implemented in
      `_detect_conflict`; all three cases tested to raise
      `ArchiveError(ErrorCategory.ARCHIVE_CONFLICT, ...)` and to leave the
      original file's content unchanged._
- [x] Never delete an archive merely because its source later disappears.
      A missing source must leave the existing archive file untouched
      until an explicit, documented revision/update action is taken.
      _Satisfied by construction: this module has no delete path at all._
- [x] Provide archive inspection that can reconstruct successful
      processing state (which memo IDs are already archived, with what
      fingerprint) from frontmatter alone, and can identify malformed or
      orphaned archive entries (e.g. a `.md` file with unparseable or
      missing frontmatter) without touching `state.json`. _`inspect_archive`
      and `rebuild_state_from_archive`, tested against valid, malformed,
      incomplete-frontmatter, and orphaned-file cases._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 5:

- [x] Markdown output is self-describing, fact-only, and robust to
      YAML/Markdown boundary cases. _True at the synthetic-test level
      (five boundary cases + Unicode); real-sample confirmation is
      Phase 9's job, consistent with how Phase 4 treated this same gap._
- [x] Interrupted writes cannot create a completed-looking partial
      archive. _Delegated to `io_utils.atomic_write`, already tested at
      that layer (`test_atomic_write_never_leaves_partial_file_on_failure`);
      this phase's own tests confirm no leftover temp file after a normal
      write and confirm the conflict-or-no-op path never calls
      `atomic_write` on an existing file at all._
- [x] Duplicate, changed, and missing source situations retain historical
      text and report an actionable conflict. _Duplicate/changed source/
      changed transcript all tested to preserve the original file's
      content and raise a structured conflict. "Missing source" itself
      isn't this module's concern — a missing source file never reaches
      `write_archive_entry` at all; the existing archive simply isn't
      touched, which is the "retain historical text" guarantee in its
      strongest form (nothing ever runs against it)._
- [x] Archive metadata can rebuild successful operational state.
      _`rebuild_state_from_archive`, tested._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-08: Created this task file. While drafting, found and closed a
  schema gap (`source_filename` missing from `yaml_meta.REQUIRED_FIELDS`)
  and confirmed `config.archive_root` already satisfies the archive-root
  requirement. No archive-writing implementation yet. Outcome: 81/81 tests
  pass; `ruff check`/`ruff format --check` clean.
- 2026-09-08 (same day, continued): Added `source_size`/`source_mtime`/
  `transcript_sha256` to `yaml_meta.REQUIRED_FIELDS` (needed for conflict
  detection and state rebuilding, not just `source_filename`). Implemented
  `archive.write_archive_entry`, `read_archive_entry`, `inspect_archive`,
  and `rebuild_state_from_archive`. Found and fixed a fidelity bug during
  testing (an unwanted auto-appended trailing newline). Wrote 20 tests in
  `tests/test_archive.py`. Outcome: 101/101 tests pass; `ruff check`/
  `ruff format --check` clean.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 5
here, per `AGENTS.md`'s working method._

- 2026-09-08: Added `source_filename`, `source_size`, `source_mtime`, and
  `transcript_sha256` to `yaml_meta.REQUIRED_FIELDS`. Not a deviation from
  the roadmap's goal — it fixes a gap against the roadmap's own explicit
  Phase 5 requirements ("Include the original source filename...",
  "Compare later source fingerprints and extracted transcript hashes...",
  "Archive metadata can rebuild successful operational state") that
  Phase 2's draft schema had missed, since Phase 5's scope didn't exist
  yet when that draft was written. Recorded here per the same "revise the
  draft rather than treat it as frozen" precedent used in
  `tasks/005-...md` and `tasks/020-...md`.
