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
