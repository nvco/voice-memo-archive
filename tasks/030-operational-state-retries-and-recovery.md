# Operational state, retries, and recovery

Focused task plan for Phase 6 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Defined `state.RecordingStatus` (a real `StrEnum`, replacing Phase 2's
  unconstrained `status: str`): `pending`, `processed`, `skipped_empty`,
  `skipped_no_transcript`, `failed`, `needs_attention`, `acknowledged`,
  `conflict` — exactly the roadmap's vocabulary. `RecordingState.from_dict`
  now validates against it (`RecordingStatus(data["status"])`), so a
  corrupted or hand-edited `state.json` with an unknown status value fails
  loudly (`StateError`) instead of silently accepting drift. Fixed
  `archive.REBUILT_STATUS` from Phase 5's `"ok"` placeholder to
  `RecordingStatus.PROCESSED` to match, and updated
  `tests/test_archive.py`/`tests/test_state.py` accordingly.
- Extended `RecordingState` with `source_filename` (so a `needs_attention`/
  `conflict` record is self-describing without re-running discovery) and
  `next_retry_at` (gates the next automatic retry attempt). Extended
  `State` with `last_scan_result_counts` and `last_scan_last_error` — the
  scan-level auditing the roadmap asks for, alongside the
  already-existing `last_scan_started_at`/`last_scan_completed_at`.
- Added four `ErrorCategory` values with no prior coverage:
  `SOURCE_INACCESSIBLE`, `SOURCE_UNSTABLE` (discovery-level transient
  conditions), `SOURCE_MALFORMED_FILENAME`, `SOURCE_UNRESOLVABLE_ID`
  (defined for taxonomy completeness; the latter two are never actually
  stored in a `RecordingState`, since those candidates have no recording
  ID to key one on — see below).
- Added `paths.format_utc_iso(dt)` — the single shared timestamp formatter
  every `state.py` timestamp field now goes through (`Z`-suffixed UTC ISO
  8601, seconds precision), so they compare and sort correctly as plain
  strings (used directly for the retry-due comparison in `scheduling.py`).
- Implemented the full orchestrator in `scheduling.py`:
  - `run_scan(config_path, state_path, *, now=None)`: acquires
    `io_utils.ScanLock`, loads state (recovering via
    `reconcile_with_archive` if `state.json` is corrupt — see below),
    calls `discovery.scan()`, dispatches every candidate through
    `_handle_candidate`, and saves the result. `now` is an injectable
    clock so retry spacing is testable without sleeping — every scheduling
    test drives it with a fixed/advancing fake clock instead of real time.
  - Status mapping (full reasoning in `scheduling.py`'s own module
    docstring): `UNCHANGED` against a prior stable status
    (`processed`/`skipped_empty`/`skipped_no_transcript`/
    `needs_attention`/`acknowledged`/`conflict`) is left completely
    untouched — no re-extraction, satisfying "normal scans do not parse
    stable successful recordings again"
    (`test_unchanged_processed_recording_is_never_reextracted` asserts
    `extraction.extract_transcript` is never called). `NEW`/`CHANGED`
    (source-file change) always gets a fresh attempt cycle regardless of
    any prior backoff state — the roadmap's "a ... source-file change
    reopens it" rule, applied uniformly, not just to `acknowledged`.
  - **A candidate with no resolvable recording ID
    (`MALFORMED_FILENAME`/`UNRESOLVABLE_ID`) is never written into
    `state.recordings` at all** — there is no ID to key a record on, so
    there is nothing to retry/exhaust/acknowledge. Instead it is reported
    directly in `run_scan`'s returned `ScanSummary.unidentified` every
    single scan for as long as the offending file exists. This is a
    deliberate design decision, not an oversight — see "Not done yet"
    below for the one exit-criterion nuance it creates.
  - `DUPLICATE_ID` and an `ArchiveError(ARCHIVE_CONFLICT, ...)` from
    `write_archive_entry` both become `RecordingStatus.CONFLICT`.
  - `ExtractionStatus.EMPTY` becomes `RecordingStatus.PENDING` the first
    time; only becomes `SKIPPED_EMPTY` once the *same* source fingerprint
    reproduces `EMPTY` on a later scan (`_handle_empty`) — the roadmap's
    "require stability across scans before classifying a source as empty"
    rule. This is a *different* stability check than discovery's existing
    same-scan two-`stat()`-reads check (`CandidateStatus.UNSTABLE`); see
    the reasoning captured before implementation, still accurate, in the
    Session log's first entry below.
  - `ABSENT`/`UNSUPPORTED` become `SKIPPED_NO_TRANSCRIPT` (a stable fact).
    `UNREADABLE`/`MALFORMED`/`INCOMPLETE`, `INACCESSIBLE`/`UNSTABLE`
    (discovery-level), and an unexpected `ArchiveError` (e.g.
    `ARCHIVE_WRITE_FAILED`) are all transient-shaped: `FAILED` with
    increasing retry spacing, escalating to `NEEDS_ATTENTION` once
    exhausted (`_transient_failure`).
  - `RETRY_DELAYS = (5 minutes, 30 minutes, 2 hours)` — three spaced,
    increasing delays, chosen as this phase's own judgment call (the
    roadmap specifies the shape, not the numbers). After the fourth
    attempt (the original plus three retries) fails, the record becomes
    `NEEDS_ATTENTION`.
  - `acknowledge(state, recording_id)`: `needs_attention` ->
    `acknowledged`, preserving every fact (retry count, error category,
    fingerprint) unchanged — acknowledgment changes visibility, not the
    underlying record.
  - `retry(state, recording_id)`: targeted manual retry from `failed`,
    `needs_attention`, or `conflict` -> `pending` (reset retry count and
    backoff), so the next scan attempts it immediately regardless of any
    delay. `retry_all_needing_attention(state)`: the bulk form.
  - `reconcile_with_archive(state, archive_root)`: rebuilds every
    `processed` record straight from `archive.rebuild_state_from_archive`
    (the archive is authoritative for success), leaving every other
    record (pending/failed/needs_attention/acknowledged/conflict — none
    of which has a completed archive file by definition) exactly as it
    was. Never touches `config.json` — settings are a different file this
    function has no path to reach, so they can't be at risk regardless of
    what `state.json` looked like. `run_scan` calls this automatically
    (starting from an empty `State()`) when `load_state` raises
    `StateError`, so a corrupt/absent `state.json` self-heals from the
    archive on the very next scan rather than needing a separate manual
    "recover" step.
- Wired `cli.py`'s `scan` subcommand to the real `scheduling.run_scan`
  (previously an unconditional `NotImplementedError` stub): prints a
  one-line result-count summary on success, prints any unidentified
  entries to stderr, and prints+returns 1 on an `ArchiveError` (e.g. a
  concurrent scan already holding the lock). `status`/`doctor` remain
  Phase 7's job, untouched.
- Found and fixed a real test-safety issue while updating `test_cli.py`:
  its scan test previously relied on `cli.py`'s *real* default config
  path, which — now that `run_scan` actually does something — would have
  made the test suite enumerate the real, configured Voice Memos
  Recordings folder on whatever machine runs it if `scan` were ever
  invoked without `--config` pointing elsewhere. Rewrote it to always
  write a synthetic `config.json` pointing at an empty `tmp_path`
  directory first.
- 16 new/changed tests: 15 in new `tests/test_scheduling.py` (end-to-end
  scans against synthetic `.m4a` containers built with the existing
  `tests/mp4_builders.py` from Phase 4, covering every status-mapping
  branch above, retry backoff/exhaustion with an injected fake clock,
  source-change reopening a `needs_attention` record, acknowledge/retry/
  bulk-retry, reconciliation, and corrupt-`state.json` recovery), plus 1
  in `test_state.py` for the new status-validation behavior.
  117 tests total; `ruff check`/`ruff format --check` clean.

**Not done yet — next action:**

- Exit criterion "a transient, empty, or failed source cannot disappear
  silently from status" is satisfied for every case *with a recording ID*
  via persisted `state.json` records, but `MALFORMED_FILENAME`/
  `UNRESOLVABLE_ID` satisfy it differently: by construction they're
  recomputed and reported fresh on every single scan (live, not
  persisted), rather than tracked/retried. This is a deliberate,
  documented design choice (see "Done" above), but it means there's no
  state file record a `status` command could show between scans — a
  future Phase 7 `status`/`doctor` command needs to either run a live
  scan itself to surface these, or this gap needs revisiting then. Noted
  here so Phase 7 doesn't lose track of it.
- No CLI surface for `acknowledge`/`retry`/`retry_all_needing_attention`/
  `reconcile_with_archive` yet — `cli.py` only wires `scan`. Per this
  project's established module-boundary precedent (Phase 3 deferred
  `first_seen_at`'s consumer to Phase 6/7; Phase 5 deferred the CLI setup
  UX for `archive_root` to Phase 7), exposing these as actual subcommands
  (`status --acknowledge <id>`, `status --retry <id>`, etc.) is Phase 7's
  "Setup, automation, and diagnostics" job — this phase only had to make
  the underlying functions exist, tested, and callable.
- None of this has been exercised against real Voice Memos recordings or
  a real multi-day retry cycle — only synthetic containers and an
  injected fake clock. Real-sample/real-timing verification is Phase 9's
  job, consistent with every other phase's synthetic-test acceptance so
  far.
- `launchd` automation itself (the actual periodic invocation of
  `run_scan`) is explicitly Phase 7's job per the roadmap's own phase
  split ("Dependencies: Phases 2, 3, and 5" for Phase 6; Phase 7 owns
  "Setup, automation, and diagnostics").

## Scope and decisions to validate

- [x] Maintain versioned operational state apart from settings through
      validated, atomic writes and a single-scan lock. _Mechanism already
      existed from Phase 2 (`state.py`'s versioned schema,
      `io_utils.atomic_write`, `io_utils.ScanLock`); `run_scan` is what
      actually drives a real scan through it, tested end-to-end._
- [x] Support `pending`, `processed`, `skipped_empty`,
      `skipped_no_transcript`, `failed`, `needs_attention`, `acknowledged`,
      and `conflict` states. Record memo ID, source filename, attempt
      count, times, next retry, and a factual, transcript-free reason.
      _`RecordingStatus` enum plus `RecordingState`'s
      `source_filename`/`retry_count`/`last_scanned_at`/`next_retry_at`/
      `last_error_category` fields (memo ID is the dict key in
      `State.recordings`, not a duplicated field)._
- [x] Require stability across scans before classifying a source as empty.
      Retry transient states with three spaced, increasing-delay
      opportunities; after that retain a `needs_attention` record rather
      than silently dropping or retrying indefinitely. _`_handle_empty`'s
      two-consecutive-scan confirmation; `RETRY_DELAYS`
      (5min/30min/2h) plus `NEEDS_ATTENTION` escalation in
      `_transient_failure`. Both tested directly with an injected clock._
- [x] Provide targeted and bulk manual retry, acknowledgment of a
      `needs_attention` item, and explicit full reconciliation. An
      acknowledgment suppresses automatic retries but retains the factual
      state until a manual retry, full rescan, or source-file change
      reopens it. Reconstruct processed status from archives when possible
      and recover from absent or corrupt `state.json` without losing user
      settings. _`acknowledge`/`retry`/`retry_all_needing_attention`/
      `reconcile_with_archive`, all tested. `run_scan` auto-recovers via
      `reconcile_with_archive` on a `StateError`; `config.json` is never
      touched by any of this, so settings can't be lost regardless._
- [x] Record scan-level auditing facts: schema version, start/end, result
      counts, and the most recent non-sensitive error. _`schema_version`/
      `last_scan_started_at`/`last_scan_completed_at` already existed;
      added `last_scan_result_counts` and `last_scan_last_error`,
      populated by `run_scan` every scan._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 6:

- [x] Normal scans do not parse stable successful recordings again.
      _`test_unchanged_processed_recording_is_never_reextracted` asserts
      `extraction.extract_transcript` is called zero times on a second
      scan of an unchanged, already-`processed` source._
- [x] A transient, empty, or failed source cannot disappear silently from
      status. _True for every case with a recording ID (persisted,
      retried, escalated to `needs_attention`). The two ID-less discovery
      statuses satisfy this via live per-scan reporting instead of
      persistence — see "Not done yet" above for the one open nuance this
      leaves for Phase 7._
- [x] Retry spacing, exhaustion, acknowledgment, manual retry, and
      source-stability behavior have automated coverage. _All five
      covered directly in `tests/test_scheduling.py`._
- [x] State recovery and archive reconciliation preserve configuration
      and archival records. _`reconcile_with_archive` never touches
      `config.json`; `test_run_scan_recovers_from_corrupt_state_json`
      confirms a corrupted `state.json` self-heals from the archive tree
      without losing the completed archive file itself._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-08: Created this task file. While drafting, found that
  `state.RecordingState.status` had no defined vocabulary yet and that
  `archive.REBUILT_STATUS = "ok"` (Phase 5) would need to change to
  `"processed"` once this phase's enum existed. No implementation yet.
- 2026-09-08 (same day, continued): Implemented the full phase —
  `RecordingStatus` enum and extended `RecordingState`/`State` fields in
  `state.py`; four new `ErrorCategory` values; `paths.format_utc_iso`;
  the complete orchestrator (`run_scan`, `acknowledge`, `retry`,
  `retry_all_needing_attention`, `reconcile_with_archive`) in
  `scheduling.py`; wired `cli.py`'s `scan` subcommand to it. Found and
  fixed a test-safety issue in `test_cli.py` (was relying on real
  Application-Support defaults). Wrote 16 new/changed tests. Outcome:
  117/117 tests pass; `ruff check`/`ruff format --check` clean.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 6
here, per `AGENTS.md`'s working method._

- 2026-09-08: `MALFORMED_FILENAME`/`UNRESOLVABLE_ID` candidates are never
  persisted into `state.recordings` (see "Done" above) — the roadmap's
  scope line ("record memo ID, source filename, attempt count...") implies
  every trackable condition gets a persisted record, but these two
  conditions have no memo ID to key one on by definition. Handling them
  via live per-scan reporting instead is a deliberate interpretation of
  an ambiguous case, not a rejection of the roadmap's intent (nothing
  "disappears silently" — it's reported every scan for as long as it
  exists) — flagged here per the "record uncertainty rather than silently
  reinterpreting" principle in `AGENTS.md`'s Decision context.
