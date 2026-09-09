# End-to-end verification and release readiness

Focused task plan for Phase 9 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

Per the 2026-09-09 decision recorded in
`tasks/040-packaging-permissions-and-privacy.md`, this project is
personal-use only for now — "release readiness" in this phase's name means
"ready for the user's own confident daily use," not a public release.

## Status

_Last updated: 2026-09-09. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Ran item 1 (the automatable subset) in full:
  - Full automated suite: 193/193 passing; `ruff check`/`ruff format
    --check` clean (re-confirmed, not just carried over from Phase 8's
    own record).
  - Repository audit: `.local/` confirmed untracked and referenced only
    by documentation *about* the ignore rule itself (`.gitignore`,
    `AGENTS.md`, `CHANGELOG.md`, `tasks/*.md`, `skills/wrap-up/SKILL.md`)
    — never as a path a tracked file actually reads from. No `.m4a`/
    `.qta`/`.wav`/`.mp3`/`.aac`/`.caf` file is tracked anywhere in the
    repo (every fixture is built programmatically by
    `tests/mp4_builders.py`, never committed as a binary sample). No
    tracked file contains a real, non-`tmp_path` filesystem path. 51
    tracked files total, all text (source, tests, or docs) — no stray
    binaries.
  - "Unintended network dependencies" audit: `pyproject.toml`'s only
    runtime dependency is `pyyaml` (a pure offline YAML library — no
    network capability of any kind); `pytest`/`ruff` are dev-only. This
    is corroborating evidence alongside Phase 8's
    `tests/test_privacy_claims.py`, which already proves no network
    socket opens at the product-behavior level, not just by dependency
    inspection.
  - Package/clean-install smoke test: a from-scratch `.venv` (outside the
    repo, since installing into it is exactly what's being tested), `uv
    pip install -e ".[dev]"`, full test suite and `ruff check` re-run
    from that fresh install, and every subcommand's `--help`
    (`scan`/`status`/`doctor`/`retry`/`acknowledge`/`reconcile`/`verify`/
    `setup`/`uninstall`) exercised through the installed
    `voice-memo-archive` console-script entry point, not just
    `python -m`. All passed. Confirms `AGENTS.md`'s documented "Development
    setup" section is still accurate after 8 phases of change.

**Not done yet — next action:**

- This phase's scope splits sharply into two kinds of work, and unlike
  every prior phase, the split doesn't run "engineering now, decision
  later" — it runs **"automatable now" vs. "requires the user's own
  hands on their own Mac with their own real recordings," which no
  session should do on its own initiative**:
  1. **Automatable now, no real personal data needed — done, see "Done"
     above:** the full automated suite; a repository/private-material
     audit; a network-dependency audit; and a from-scratch clean-install
     smoke test through the real console-script entry point.
  2. **Requires the user, not this session, to actually do it:** granting
     Full Disk Access to whatever process runs the tool (a real System
     Settings action); running `setup` for real against the real
     `~/Library/Group Containers/.../Recordings` folder; running `scan`
     for real and inspecting the real archived output; and populating the
     roadmap's own "manual verification matrix" (real mono/stereo/spatial
     `.m4a`/`.qta`, delayed download, missing transcript, empty source,
     source change, permission denial, service restart, acknowledgment,
     state recovery) against real synced recordings. **This session
     should never run `setup`/`scan` against real Voice Memos data on its
     own initiative** — per this project's own privacy-first purpose and
     this session's general "actions with care" discipline, touching real
     personal recordings is the user's action to take and direct, not
     something to do as a side effect of "finishing a phase." If the user
     wants help running through this, that's a live, guided session, not
     autonomous work.
- Item 1 is done (see "Done" above). Item 2 needs the user to actually sit
  down and do it (with this session guiding/troubleshooting if wanted,
  not doing it unattended).

## Scope and decisions to validate

- [ ] Maintain a manual verification matrix for macOS, source-device
      transcript availability, language/region, real synced mono, stereo,
      and spatial `.m4a` and `.qta`, delayed download, missing transcript,
      empty source, source change, permission denial, service restart,
      acknowledgment, and state recovery. Real samples remain local and
      are never committed. _Needs the user — see "Not done yet" above._
- [x] Run the full automated suite, package smoke tests, clean-install
      test, and repository audit for private fixtures and unintended
      network dependencies.
- [ ] Review setup, normal workflow, recovery, privacy, support matrix,
      limitations, and removal documentation. _`AGENTS.md`'s developer-
      facing setup docs are confirmed accurate (the clean-install smoke
      test above exercises them directly); the user-facing public
      documentation this line really means is Phase 8's deferred scope —
      not relevant while this stays personal-use only._
- [ ] Convert each verified defect or important gap into a new numbered
      task plan before release; do not hide it in release notes.

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 9:

- [ ] At least one real synced `.m4a` and one real synced `.qta` complete
      the archive flow with their visible Apple transcript preserved.
- [ ] Expected non-success states are visible and repairable. _Every
      status is automated-test-covered (Phase 6/7); "visible and
      repairable" in the fullest sense — a real `needs_attention` record
      a human actually looks at and resolves — needs a real run._
- [x] No personal audio, transcript, title, identifier, or raw private
      note is tracked in Git. _Confirmed directly by the repository audit
      above: no tracked `.m4a`/`.qta`/audio file of any kind, no tracked
      real filesystem path, `.local/` untracked and unreferenced except
      by documentation describing the rule itself._
- [ ] Release documentation and known limitations are ready for public
      review. _Not relevant while personal-use only — see Phase 8._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-09: Created this task file. No implementation yet.
- 2026-09-09 (same day, continued): Ran the automatable subset —
  automated suite, repository/private-material audit, network-dependency
  audit, and a from-scratch clean-install smoke test through the real
  console-script entry point. All passed; no findings. The remaining
  scope needs the user to run the tool for real against real recordings,
  which this session deliberately did not do on its own initiative.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 9
here, per `AGENTS.md`'s working method._

(none yet)
