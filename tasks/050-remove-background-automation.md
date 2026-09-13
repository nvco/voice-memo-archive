# Remove background automation

Not a phase of the original 9-phase roadmap in `tasks/000-initial-build.md`
— Phase 7 (`tasks/035-...md`) built `launchd` background automation, and
this task removes it. Numbered like the phase files (rather than left
unnumbered like `future-ai-summary-skill.md`) because it's active work
changing something the roadmap already shipped and verified, not an
unstarted future idea.

## Why

Recorded in detail in `tasks/040-packaging-permissions-and-privacy.md`'s
2026-09-12 session log entries. Summary: after actually enabling background
automation for real, the user found the whole posture — settings spread
across `~/Library/Application Support`, `~/Library/LaunchAgents`,
`~/Library/Logs`; a macOS "unidentified developer" Background Items
warning; a single, globally-labeled `launchd` job that a scratch test run
silently overwrote — added more complexity than value for what this
project's `AGENTS.md` decision context calls "a privacy-first macOS
utility," used personally, not distributed to a general audience. A
scheduled-AI-agent alternative was considered and rejected (still needs
*some* OS-level scheduler underneath; unclear it would even run locally
with filesystem access rather than in a cloud sandbox). Net decision,
2026-09-12: drop background automation entirely. This tool is a one-shot,
user-invoked CLI; the user runs `scan` manually whenever they want new
recordings pulled in.

## Status

_Last updated: 2026-09-12. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Deleted `src/voice_memo_archive/launchd.py` and `tests/test_launchd.py`
  entirely.
- Removed `schedule_mode`/`scan_interval_seconds` from `config.Config`
  (and their validation in `from_dict`) — `config.py` now silently ignores
  either key if still present in an old `config.json` (added
  `test_load_config_ignores_legacy_schedule_fields` to prove it), so no
  migration was needed. The real config.json this project was tested
  against (this user's own machine) still has both leftover keys; they're
  now simply unread, not something requiring manual cleanup.
- Removed the same two fields from `setup.SetupPlan`/`build_setup_plan`/
  `commit_setup`.
- Removed `diagnostics.check_scheduler` and its `launchd` import;
  `run_doctor` no longer includes a `scheduler` check.
- `cli.py`: removed `_cmd_uninstall` and the `uninstall` subcommand
  entirely (its only job was removing the `launchd` plist, plus an
  optional `--purge-config` convenience — with no plist left to remove,
  a dedicated subcommand for deleting two JSON files was no longer worth
  keeping; see README's Uninstalling section for the manual `rm`
  instead). Removed `--schedule-mode`/`--scan-interval`/`--enable-now`
  from `setup`'s arguments. Removed the two schedule/interval rows from
  the settings menu (`_format_setup_menu`/`_edit_setup_menu`) and the
  now-unused `_prompt_int` helper. `setup` no longer writes or mentions
  any `launchd` plist at all — it just writes `config.json` and prints a
  reminder to run `scan`.
- Updated doc comments in `scheduling.py` (`launchd` was described as a
  future caller of `run_scan`) and `cli.py`'s module docstring
  (previously described the plist-write/`--enable-now` split in detail).
  Left `io_utils.py`'s Phase 2 exit-criterion quote alone — it's a direct
  quote of `tasks/000-initial-build.md`'s own historical text, still
  accurate as a citation.
- Updated `AGENTS.md`'s project invariant: "Provide a command-line
  interface and user-level `launchd` automation" → "Provide a
  command-line interface only... there is no background/scheduled
  automation," pointing here.
- Updated `README.md`: Setup section no longer describes a Schedule
  prompt or `--enable-now`/Gatekeeper disclosure (moot — there's nothing
  to enable); Uninstalling section replaced with a plain `rm` of the two
  settings files, since there's no service to uninstall; Known
  limitations' "unidentified developer" bullet removed.
- Test fallout fixed across `tests/test_config.py`, `tests/test_setup.py`,
  `tests/test_cli.py`, `tests/test_diagnostics.py`,
  `tests/test_privacy_claims.py` — every `launchd` import/mock removed;
  `test_setup_interactive_menu_seeds_defaults_from_existing_config`
  rewritten to carry `import_mode` across runs instead of `schedule_mode`
  (same "seed from existing config" behavior, different field, since
  `schedule_mode` no longer exists to prove it with).
- Outcome: 176/176 tests pass (down from 197 — net removal of coverage
  for a removed feature, not a coverage gap); `ruff check`/`ruff format
  --check` clean.

**Not done yet — next action:**

- This user's own real machine still has a `config.json` with the two
  now-ignored legacy keys sitting in it (harmless, per the "ignores
  legacy fields" behavior above) — left as-is per the user's own explicit
  decision not to relocate/edit it further (see `tasks/040-...md`'s final
  session log entry).
- `tasks/000-initial-build.md`'s Phase 7/Phase 8 sections still describe
  and check off the original `launchd` feature as built — deliberately
  *not* rewritten here; see this file's "Relationship to the original
  roadmap" section below for why.

## Relationship to the original roadmap

`tasks/000-initial-build.md`'s Phase 7 goal, scope, and exit criteria
(and Phase 8's "run unattended through `launchd`" Definition-of-done
bullet) describe `launchd` automation as built and verified — which was
true at the time. This file does not go back and un-check those boxes or
rewrite that history: Phase 7 really was completed as originally
described; this is a later, separate decision to remove what was built,
not a correction of a mistake. A pointer to this file has been added to
`tasks/000-initial-build.md`'s Plan history instead, so a reader of the
original roadmap can find out the feature was later removed without the
roadmap's own historical record being altered.

## Exit criteria

- [x] `launchd.py` and every reference to it (code, tests, config schema,
      CLI flags) are gone.
- [x] Full test suite passes; lint/format clean.
- [x] `AGENTS.md`'s project invariants no longer require background
      automation.
- [x] `README.md` accurately describes the tool as manual-only, with no
      stale mention of `--enable-now`, the Gatekeeper warning, or the
      `uninstall` command.
- [x] `CHANGELOG.md` has an entry for this removal.

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-12: Discussed at length in `tasks/040-...md` (real background
  automation friction → considered and rejected a scheduled-AI-agent
  alternative → decided to drop automation entirely, personal-use
  decision, not a project capability the user wants at all). User then
  asked "what's the point of having it" about the unused config fields,
  which escalated on explicit confirmation to removing the whole feature
  from the codebase. Implemented the full removal described above in one
  session. Deliberately chose to also remove the `uninstall` subcommand
  entirely (its only remaining purpose without `launchd` was optionally
  deleting two JSON files, which a user can do directly) rather than
  keep a narrower "purge config" command — flagged here in case that
  judgment call should be revisited.
