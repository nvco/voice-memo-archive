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
- Phase 1 (in progress): began real-fixture inspection under
  `tasks/005-platform-feasibility-and-data-contract.md`. Confirmed Full
  Disk Access is required (with no programmatic prompt) to read the
  configured Recordings folder; confirmed `.m4a` carries mono/stereo audio
  in a single track while `.qta` carries a spatial dual-track layout
  (stereo AAC + ambisonic); found that a recording's filename can omit its
  ID suffix when a `.composition/manifest.plist` sidecar exists, with the
  canonical ID recoverable from that sidecar instead. See the task file for
  full findings and remaining open items (transcript-payload location is
  still unprobed).
