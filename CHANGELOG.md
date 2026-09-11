# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries summarize
completed outcomes; roadmap/sequencing rationale lives in the build plan's
own "Plan history," and per-task deviations live in each task-plan file.

## [Unreleased]

### Added

- Phase 0: Committed the public repository baseline (`.gitignore`, `AGENTS.md`,
  `CLAUDE.md`, `tasks/000-initial-build.md`). Verified `.local/` is ignored
  and unreferenced by any tracked file, and that the repository contains no
  source code, dependencies, or configuration capable of a network call or
  Voice Memos database access.
- Added `CHANGELOG.md` and a repository-hygiene rule in `AGENTS.md` requiring
  an entry when a phase or other meaningful change completes.
- Added the `wrap-up` project skill (`skills/wrap-up/SKILL.md`, symlinked at
  `.claude/skills/wrap-up`): an end-of-session checkpoint that updates the
  active task file's Status section and proposes a commit, so a new session
  can pick up exactly where the previous one left off.
- Added a matching `.agents/skills/wrap-up` symlink so Codex CLI (which
  discovers skills via `.agents/skills`, not the root `skills/` folder) can
  find the same skill. Added `skills/README.md` pointing back to AGENTS.md's
  "Shared skills" section so the symlink layout isn't mistaken for
  duplication.
- Phase 1 (in progress): began real-fixture inspection under
  `tasks/005-platform-feasibility-and-data-contract.md`. Confirmed Full
  Disk Access is required (with no programmatic prompt) to read the
  configured Recordings folder; confirmed `.m4a` carries mono/stereo audio
  in a single track while `.qta` carries a spatial dual-track layout
  (stereo AAC + ambisonic); found that a recording's filename can omit its
  ID suffix when a `.composition/manifest.plist` sidecar exists, with the
  canonical ID recoverable from that sidecar instead. See the task file for
  full findings and remaining open items.
- Phase 1 (in progress): probed and confirmed the native transcript's
  container location and JSON shape on real `.m4a` and `.qta` samples —
  `.m4a` carries it in a direct `tsrp` box, `.qta` carries it via a
  metadata-keyed entry, and both encode the same locale/timed-run JSON
  schema. See the task file's Findings for the full structural detail and
  the Phase 2 parsing implications it leaves open.
- Phase 1: drafted a support matrix from accumulated findings, then closed
  out remaining sample-dependent gaps (non-`en_US` locale, in-progress
  iCloud download, absent/malformed/incomplete transcript cases) as
  deliberately deprioritized rather than blocking further work — see the
  task file's Deviations section.
- Phase 2 (started): chose Python as the implementation language/toolchain
  and created `tasks/010-foundation-and-test-harness.md`.
- Phase 2 (complete): built the Python package skeleton
  (`src/voice_memo_archive/`) with module boundaries for config, state,
  discovery, extraction, archiving, scheduling, and diagnostics; a thin
  CLI that only calls into them. Implemented versioned `config.json`/
  `state.json` schemas with a tested generic migration chain, atomic
  writes, a stale-lock-reclaiming scan lock, filename/path/date utilities,
  a structured error taxonomy that keeps transcript-adjacent detail out of
  default log output, and versioned YAML-frontmatter metadata handling.
  43 tests, `ruff` lint/format clean, verified reproducible from a
  from-scratch `.venv` rebuild. Documented dev setup in `AGENTS.md`.
- Phase 3 (in progress): implemented `discovery.py` — read-only recordings
  enumeration, the confirmed exclusion list, composition-sidecar ID
  resolution for ID-less filenames, duplicate-ID detection, and
  fingerprint-based new/unchanged/changed/unstable/inaccessible
  classification. Extended `state.RecordingState` with source
  fingerprint and first-seen fields. 17 new tests (60 total); read-only
  guarantee verified directly. See
  `tasks/015-file-discovery-and-source-metadata.md` for what's still open
  (import-mode cutoffs, real delayed-download verification).
- Phase 4 (complete): implemented `extraction.py` — a bounded ISO-BMFF/
  QuickTime atom walker covering both confirmed transcript lookup paths
  (`.m4a`'s direct `tsrp` box, `.qta`'s `mdta`-keyed `meta`/`keys`/`ilst`
  chain), searching every track rather than assuming the first one. All
  seven extraction statuses (`ok`/`empty`/`absent`/`unreadable`/
  `malformed`/`incomplete`/`unsupported`) implemented and tested. Revised
  three parts of Phase 1's draft extraction contract during
  implementation (see `tasks/005-...md`). Added
  `tests/mp4_builders.py`, a from-scratch synthetic container builder,
  and 21 tests covering every status, Unicode fidelity, bounded failure
  on a corrupted container, and runtime proof of no network/database
  access. 81 tests total; `ruff` lint/format clean.
- Phase 5 (complete): implemented `archive.py` — deterministic
  `YYYY/MM/DD/HHMMSS-<recording_id>.md` archive output via
  `yaml_meta.dump_metadata` and `io_utils.atomic_write`, conflict
  detection for a changed source, a changed transcript, or a duplicate
  memo ID (each raising a structured `ArchiveError` and leaving the
  existing file untouched rather than overwriting), and archive
  inspection/reconciliation (`inspect_archive`,
  `rebuild_state_from_archive`) that classifies every file in the
  archive tree and can rebuild per-recording operational state from
  frontmatter alone. Extended `yaml_meta.REQUIRED_FIELDS` with
  `source_filename`, `source_size`, `source_mtime`, and
  `transcript_sha256` to close gaps against Phase 5's own requirements
  that Phase 2's draft schema had missed. 20 new tests in
  `tests/test_archive.py` (101 total); `ruff` lint/format clean. See
  `tasks/025-archive-output-and-deduplication.md` for what's still open
  (orchestration wiring is Phase 6's job; real-sample verification is
  Phase 9's).
- Phase 6 (complete): implemented the scan orchestrator in
  `scheduling.py` — `run_scan` drives `discovery.scan()`,
  `extraction.extract_transcript()`, and `archive.write_archive_entry()`
  under `io_utils.ScanLock`, mapping every outcome onto a new
  `state.RecordingStatus` vocabulary (`pending`/`processed`/
  `skipped_empty`/`skipped_no_transcript`/`failed`/`needs_attention`/
  `acknowledged`/`conflict`, replacing Phase 2's unconstrained status
  string). Stable successful recordings are never re-parsed; an empty
  transcript requires two consecutive confirming scans before being
  finalized `skipped_empty`; transient failures get three spaced,
  increasing-delay retries before escalating to `needs_attention`; a
  source-file change reopens processing immediately regardless of any
  backoff in progress. Added targeted/bulk manual retry, acknowledgment,
  and archive-based reconciliation (which `run_scan` also uses to
  self-heal automatically from a corrupted `state.json`, never touching
  `config.json`). Wired `cli.py`'s `scan` subcommand to the real
  implementation. 16 new/changed tests, largely end-to-end scans against
  synthetic containers with an injected fake clock (117 total); `ruff`
  lint/format clean. See `tasks/030-operational-state-retries-and-recovery.md`
  for what's still open (CLI surface for retry/acknowledge and `launchd`
  automation are Phase 7's job).
- Phase 7 (complete): added the setup flow (`setup.py`), user-level
  `launchd` automation (`launchd.py`), extended diagnostics
  (`diagnostics.run_doctor`), and the full CLI command surface
  (`setup`, `scan` [now with `--force`], `status`, `doctor`, `retry`,
  `acknowledge`, `reconcile`, `verify`). `config.json` gained
  `import_mode`/`import_since`/`setup_completed_at`/`schedule_mode`/
  `scan_interval_seconds`; a new import-mode cutoff filter in
  `scheduling.py` supports all/new-only/date initial-import scoping,
  filtering on each recording's own `recorded_at` rather than discovery
  time so a delayed iCloud download is never mistaken for "new."
  `launchd`'s plist is always written (idempotent, file-only) but only
  ever registered with the running `launchd` behind an explicit
  `--enable-now` and confirmation — never invoked for real against this
  machine while building or testing this phase. Found and fixed two real
  gaps along the way: a malformed `import_since`/`setup_completed_at` in
  `config.json` now fails at load time instead of crashing a scan later,
  and `doctor` no longer falls back to guessing the real default
  recordings folder when `config.json` is corrupt (which would have
  silently checked the wrong folder — and would have made the test suite
  itself scan a real machine's actual Voice Memos folder, caught before
  it ever ran). 182 tests total (up from 126); `ruff` lint/format clean.
  See `tasks/035-setup-automation-and-diagnostics.md` for what's still
  open (real `launchd`/first-run verification is Phase 9's job).
- Phase 8 (complete): added `cli.py`'s `uninstall` subcommand — removes
  the `launchd` registration/plist (and, only with an explicit
  `--purge-config` flag, `config.json`/`state.json`) while never reading
  `archive_root` at all, so "uninstalling must not delete the user's
  archive" is a structural guarantee rather than a redaction to get
  right. Added `tests/test_privacy_claims.py`, proving at the product
  (`cli.py`) level — not just one module — that no command ever opens a
  network socket and that transcript content never appears in any
  command's output, including after a real `processed` archive write (a
  first draft of these tests had a bug that made them pass trivially by
  accident, without ever exercising a real successful extraction —
  caught and fixed before landing). Decided the distribution form —
  source install (`git clone` + `pip install`), raised to the user rather
  than guessed at — and added `README.md` plus a `readme` field in
  `pyproject.toml` documenting install, setup, everyday use, privacy
  guarantees, and uninstall behavior. No code signing/notarization
  applies to this distribution form; it does require Python 3.11+
  already present, named as a plain prerequisite rather than glossed
  over. 193 tests total; `ruff` lint/format clean. See
  `tasks/040-packaging-permissions-and-privacy.md`.
- Phase 9 (complete): ran the automatable half of end-to-end verification
  — the full 193-test suite from a from-scratch `.venv` install (`uv pip
  install -e ".[dev]"`, exercised through the real `voice-memo-archive`
  console-script entry point, not just `python -m`, confirming every
  subcommand's `--help` works and `AGENTS.md`'s documented setup steps
  are still accurate); a repository audit confirming no personal
  audio/transcript file, real filesystem path, or `.local/` reference is
  tracked in Git; and a dependency audit confirming the only runtime
  dependency (`pyyaml`) has no network capability. Then, live with the
  user, ran real verification against this machine's actual Voice Memos
  folder: `setup` (date-cutoff import, chosen by the user), `scan` (16
  processed — 6 real `.m4a` + 10 real `.qta`, each with verified non-empty
  transcript content and correct metadata — 3 pending, 2
  skipped_no_transcript), a repeat `scan` (empty-transcript recordings
  correctly confirmed to `skipped_empty`, no duplication), and `scan
  --force` (first real-environment exercise of the full-rescan feature,
  correct behavior, no duplication). Investigated and resolved a
  real-data question (why the archive is unparagraphed while the Voice
  Memos app shows paragraphs) by decoding the real file's full box
  structure directly plus independent web research — confirmed no
  paragraph data exists in Apple's own stored file, so the archive is
  already a faithful, complete copy. Recorded two follow-ups for later
  rather than building them now: a setup-UX gap (`setup` should prompt
  interactively, not just accept flags — see
  `tasks/035-setup-automation-and-diagnostics.md`) and a new idea for a
  sample AI-summary skill over the archive (see
  `tasks/future-ai-summary-skill.md`, deliberately unnumbered). See
  `tasks/045-end-to-end-verification-and-release-readiness.md`.
- Closed the Phase 7 setup-wizard gap: `setup` now prompts interactively
  for any value not given via `--flag` (recordings source, archive
  destination, import mode/date, schedule mode, scan interval), defaulting
  each prompt to the current `config.json`'s value when one exists (else
  the package default), so re-running `setup` and accepting every default
  except the one setting you want to change is now the natural way to
  reconfigure. `--yes` remains fully non-interactive for scripted use.
  196 tests total; `ruff` lint/format clean. See
  `tasks/035-setup-automation-and-diagnostics.md`.
