# Empty-archive command

Not a phase of the original 9-phase roadmap in `tasks/000-initial-build.md`.
Numbered like the phase files (rather than left unnumbered like
`future-ai-summary-skill.md`) for the same reason as
`tasks/050-remove-background-automation.md`: it's active work changing a
behavior the roadmap originally specified, not an unstarted future idea.

## Why

`tasks/000-initial-build.md` Phase 5 says: "Never delete an archive merely
because its source later disappears. Preserve the existing archive until a
documented, explicit revision/update action is chosen." This command is
exactly that documented, explicit action — not a contradiction of the
Phase 5 invariant, its fulfillment.

The need: immediately after
`tasks/050-remove-background-automation.md` (dropping background
automation) and wiping this user's real archive/config/state for a fresh
start, the user described their actual intended workflow — pull
transcripts into the archive, import that content into a separate
personal system ("my memory system"), and then have no further need for
the `.md` files sitting in the archive folder. They explicitly do not want
the archive to be a required permanent store for their use of this tool,
overriding this project's own default framing ("the archive is the source
of truth") for their personal setup, on purpose and with the tradeoff
understood (this was discussed directly — see the conversation this
session log entry summarizes).

## Status

_Last updated: 2026-09-13. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Added `archive.empty_archive(archive_root) -> EmptyResult` (deleted_count,
  left_count). Reuses `inspect_archive` so it only ever deletes files this
  tool already recognizes as its own — valid *and* malformed `.md` entries
  — and leaves anything orphaned (non-`.md`) exactly where it is, counted
  but untouched. Also removes any date-tree subdirectories left empty
  afterward, without touching a directory that still holds an orphaned
  file.
- Added `cli.py`'s `empty` subcommand: prints the count to be deleted (and
  how many unrecognized files will be left alone) before asking "Proceed?
  [y/N]" — skippable with `--yes` for scripted/repeated use, matching
  `setup`'s existing confirmation pattern. Never reads or writes
  `state.json`; never even takes a `--state` argument, structurally
  impossible for it to touch state accidentally, same discipline the old
  `uninstall` command used for `archive_root`.
- Deliberately a separate top-level command, not a flag on `verify` or
  `reconcile` — a destructive action should never be one accidental flag
  away from a routine diagnostic one.
- Updated `archive.py`'s module docstring (previously said a completed
  archive file is "never overwritten or deleted" — now scoped to "never
  ... as a side effect of scan/write_archive_entry," with `empty_archive`
  named as the one deliberate exception) and `AGENTS.md`'s invariants
  (added: `scan` never deletes; `empty` is the one explicit exception).
- Tests: `tests/test_archive.py` (4 new: deletes valid+malformed but not
  orphaned; removes now-empty date directories; leaves a directory alone
  if an orphaned file still lives in it; no-op on a missing archive_root)
  and `tests/test_cli.py` (4 new: nothing-to-delete message; `--yes`
  deletes and reports the count; declining leaves the file in place;
  config.json/state.json are provably untouched after emptying).
- Documented in `README.md` (new "Clearing the archive" subsection under
  Everyday use).
- Manually verified end-to-end against a scratch archive: created a
  malformed entry, confirmed `verify` saw it, declined `empty` (nothing
  deleted), ran `empty --yes` (deleted, directories cleaned up), verified
  `verify` afterward reports a clean empty archive, and confirmed
  `config.json` survived while `state.json` (never created by `setup` in
  the first place, by existing design) was correctly absent either way.
- Outcome: 184/184 tests pass; `ruff check`/`ruff format --check` clean.

**Not done yet — next action:**

- `empty` itself hasn't been run against this user's real archive yet —
  only scratch/synthetic paths so far. (`scan` *has* since run for real
  post-wipe, without ever re-running `setup` — the user relied on
  `load_config`'s package defaults, which worked as designed — and
  produced 20 real archived transcripts. `empty` against that real
  archive is still an open, easy next step whenever the user wants to
  actually use the staging-area workflow for real.)
- No flag to also reset `state.json` in the same step. Deliberately left
  out: the design intent is that a recording already marked `processed`
  should *stay* marked that way after `empty`, so a normal `scan`
  afterward treats it as already-handled rather than re-adding it to the
  now-empty archive. If a future workflow needs a true full reset
  (archive + state together), that's a distinct, separate ask — not
  something to fold into `empty` silently.

## Exit criteria

- [x] `empty` deletes only files this tool recognizes as its own; anything
      else in the archive folder is left alone and reported.
- [x] `empty` never touches `config.json` or `state.json` under any
      circumstance — provable structurally (no `--state` argument exists
      on the subcommand at all), not just by convention.
- [x] Confirmation required by default; `--yes` for scripted use, matching
      the rest of this project's destructive/consequential commands.
- [x] Full test suite passes; lint/format clean.
- [x] `README.md`/`AGENTS.md` updated to describe the new command and the
      invariant it's the one exception to.

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-13: Discussed and implemented in one session, directly following
  `tasks/050-remove-background-automation.md`'s work and this user's real
  archive/config/state wipe (see that file's context). Initially
  misunderstood the request as wanting to delete recordings from the
  actual Voice Memos app folder — pushed back hard on that specific
  misreading (would have violated the read-only Voice Memos invariant and
  risked corrupting the app's own database/iCloud sync) before the user
  clarified they meant this tool's own archive output folder only, which
  is a completely different and much lower-risk request. Built, tested,
  and documented the same session.
