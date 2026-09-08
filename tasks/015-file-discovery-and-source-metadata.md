# File discovery and source metadata

Focused task plan for Phase 3 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- `discovery.py` implemented: enumerates the configured recordings folder
  (`Path.iterdir()`, read-only), skips the exclusion-list entries confirmed
  in `tasks/005-...md` Findings (`*.waveform`, `*.composition/`, `Capture/`,
  `CaptureRecovery/`, `.CloudRecordings_SUPPORT/`, `CloudRecordings_ckAssets/`,
  `CloudRecordings.db*`), and only considers `.m4a`/`.qta` files
  (case-insensitive extension match via `paths.SUPPORTED_EXTENSIONS`).
- Filename parsing reuses `paths.parse_recording_filename` (built in
  Phase 2) for the date/time/ID/extension grammar.
- Dedup identity: the filename's ID suffix, or — for an ID-less filename —
  `RCSavedRecordingUUID` read from the adjacent
  `<timestamp>.composition/manifest.plist` sidecar via `plistlib` (matches
  the S5 finding in `tasks/005-...md`). Never guesses a substitute ID: a
  missing/unreadable sidecar or missing key classifies as
  `UNRESOLVABLE_ID`, not a fabricated identity.
- Duplicate-ID detection: any recording ID seen more than once in one scan
  flags every occurrence as `DUPLICATE_ID`, with sibling paths (redacted)
  recorded in `detail` — deliberately not picking a "canonical" one.
- Fingerprint-based change classification: a two-read `stat()` (separated
  by `stability_check_delay`, default 0.2s) yields `(size, mtime)`;
  compared against `state.RecordingState.source_size`/`source_mtime` (new
  fields added to the state schema this session — no migration needed
  since nothing has shipped against schema v1 yet) to classify each
  candidate as `NEW`, `UNCHANGED`, or `CHANGED`. Two reads disagreeing
  classifies as `UNSTABLE` (e.g. still downloading/writing); a `stat()`
  failure classifies as `INACCESSIBLE`.
- Malformed filenames classify as `MALFORMED_FILENAME` rather than being
  silently skipped or guessed at.
- Deterministic ordering: entries are processed in sorted-name order, not
  raw filesystem iteration order.
- Read-only guarantee tested directly: `test_scan_never_writes_renames_or_deletes`
  monkeypatches every mutating `os`/`Path` call discovery could plausibly
  reach and asserts a full scan over a mixed synthetic tree never touches
  any of them.
- 17 new tests in `tests/test_discovery.py` (60 total in the suite);
  `ruff check`/`ruff format --check` clean.

**Not done yet — next action:**

- `first_seen_at` (added to `RecordingState` this session) is not yet
  *written* anywhere — `discovery.scan()` is read-only and doesn't touch
  `state.json` itself. Setting it is the scan-orchestration caller's job
  (Phase 6/7), the first time a `NEW` candidate is recorded into state.
  This is a deliberate module-boundary choice, not an oversight — noted
  here so Phase 6/7 doesn't lose track of it.
- The `UNSTABLE` (delayed-download) classification mechanism is
  implemented and unit-tested (via monkeypatching the stability check),
  but — consistent with `tasks/005-...md`'s deviation — has not been
  exercised against a real in-progress iCloud download, since no such
  sample exists to test with. Left as an accepted gap, not a blocker.
- No actual "import mode" (all-history vs. new-since-setup) exists yet.
  Phase 3 only built the underlying mechanism (`first_seen_at`, fingerprint
  comparison) a future cutoff can be computed from; the mode itself, and
  its user-facing choice, belong to Phase 7 (its stated goal: "Make
  first-run choices... understandable").
- Discovery has never been run against the real, configured Recordings
  folder — only synthetic `tmp_path` trees. Real-folder exercise happens
  naturally once Phase 6/7 wires a CLI command to call `discovery.scan()`.

## Scope and decisions to validate

- [x] Enumerate only `.m4a` and `.qta` within the configured source
      directory. Normalize filename case and parse date, time, format, and
      memo ID using a documented grammar.
- [x] Use the filename memo ID as the normal deduplication identity.
      Detect malformed filenames and duplicate IDs; do not guess a
      replacement identity.
- [ ] Define how a filename's local timestamp maps to date folders, import
      cutoffs, DST boundaries, and time-zone metadata. Do not invent a UTC
      offset when it is not available from the source. _Date-folder
      mapping (`paths.archive_date_parts`) and the no-invented-offset rule
      (recorded as a naive ISO string, `recorded_at_iso`, no fabricated
      timezone) are both in place from Phase 2/3. Import cutoffs remain
      the open item above — left unchecked until Phase 7 defines the
      actual cutoff semantics against the `first_seen_at` mechanism built
      here._
- [x] Capture inexpensive source metadata/fingerprints needed to identify
      new, changed, and stable files. _`(size, mtime)` fingerprinting and
      `NEW`/`UNCHANGED`/`CHANGED` classification implemented and tested.
      Whether a caller actually skips reopening `UNCHANGED` candidates is
      enforced by the Phase 6 scan orchestrator, not this module — this
      module only provides the classification it needs to do so._
- [ ] Snapshot first-run candidates. "New recordings only" means created
      after setup, not an old memo that completed iCloud download after
      setup. Date-cutoff inclusivity must be explicit in the user
      experience. _Mechanism (`first_seen_at`) exists in the state schema;
      nothing sets or reads it yet. Left unchecked — this is genuinely a
      Phase 6/7 integration, not something Phase 3 alone can complete._
- [x] Classify inaccessible, changing, malformed, ID-colliding, and
      delayed-download files for later retry and conflict handling.

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 3:

- [x] Discovery has no write, rename, delete, or database-modification
      path under Voice Memos storage. _Verified by code (no mutating call
      anywhere in `discovery.py`) and by
      `test_scan_never_writes_renames_or_deletes`._
- [x] Candidate status is deterministic and carries sufficient factual
      information for retries and conflicts. _`Candidate` carries id,
      path, format, timestamp, fingerprint, and structured `detail`;
      ordering is sorted and tested._
- [ ] Import modes remain correct when source delivery is delayed. _No
      import mode exists yet to verify this against (see "Not done yet"
      above) — genuinely open, not yet applicable._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-08: Implemented `discovery.py` (candidate enumeration,
  classification, duplicate-ID detection, composition-sidecar ID
  resolution) and extended `state.RecordingState` with
  `source_size`/`source_mtime`/`first_seen_at`. Wrote 17 tests in
  `tests/test_discovery.py` covering exclusion, extension filtering,
  every `CandidateStatus`, deterministic ordering, and the read-only
  guarantee. Outcome: 60/60 tests pass; `ruff check`/`ruff format --check`
  clean.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 3
here, per `AGENTS.md`'s working method._

(none yet)
