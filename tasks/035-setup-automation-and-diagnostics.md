# Setup, automation, and diagnostics

Focused task plan for Phase 7 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-12. Read this section first in a new session to see
what's done and what to do next._

**2026-09-12 redesign:** the fixed-order sequential interactive prompt flow
built on 2026-09-10 (below) has been replaced with a single-screen menu:
`setup` (without `--yes`) now prints every setting with its current value at
once — flags, then existing `config.json`, then the package default, in
that priority — and lets the user pick a row by number to change, in any
order, repeating until they press Enter to continue to the existing
candidate-count preview and confirm-or-cancel step. Choosing `import_mode`
`date` still immediately asks for `import_since` right there, matching the
old flow's dependent-field behavior. This was the user's explicit request
("just a simple menu where you see all options and the selected values next
to them"), not a defect found in the sequential version — see the 2026-09-12
session log entry for what changed in `cli.py`/`tests/test_cli.py`. Below,
"real interactive prompts (as of 2026-09-10)" describes the flow this
replaced; the menu is now the actual interactive behavior.

**Done:**

- Extended `config.Config` with the fields the setup flow and `launchd`
  automation need: `import_mode` (`all`/`new_only`/`date`), `import_since`
  (`"YYYY-MM-DD"`, required only for `date`), `setup_completed_at` (the
  cutoff `new_only` filters against), `schedule_mode`
  (`monitoring`/`scheduled`), and `scan_interval_seconds`. All five use
  `.get()`-with-default in `from_dict` (not the bracket-required style
  `recordings_source`/`archive_root` use), so a `config.json` written
  before this phase keeps loading with no migration. `import_mode`/
  `schedule_mode`/`scan_interval_seconds` are validated against known
  values at load time; `import_since`/`setup_completed_at` are validated
  as parseable dates/timestamps at load time too — found and closed a real
  gap here: without that check, a malformed value wouldn't have failed
  until `scheduling.import_cutoff_date` tried to parse it mid-scan, as a
  bare unwrapped `ValueError` instead of a clean `ConfigError`.
- Implemented the import-mode cutoff filter in `scheduling.py`
  (`import_cutoff_date`, `passes_import_cutoff`), wired into `run_scan`:
  a *newly discovered* candidate (no prior state record — the "grandfather
  rule": changing `import_mode` later never retroactively excludes
  something already being tracked) is silently skipped — never persisted,
  never reported as a problem — if its own `recorded_at` falls before the
  cutoff. Filters on `recorded_at` (a permanent historical fact), never
  `first_seen_at`/discovery time, so a memo that merely finishes a delayed
  iCloud download late is still correctly excluded rather than mistaken
  for "new" — the exact distinction the roadmap's Phase 3 scope calls out.
  Day-granularity by design (matches how both modes are expressed to the
  user, as a plain calendar date/day).
- Implemented `setup.py`: `build_setup_plan` (validates options, computes
  the candidate-count preview via `discovery.scan` + the same
  `passes_import_cutoff` filter, flags whether `archive_root` resolves
  under `~/Documents`, no side effects at all) and `commit_setup` (the
  only function that writes `config.json`) — split in two specifically so
  the CLI can show a preview and let the user cancel before anything is
  written, satisfying "users see what initial import will consider before
  it begins" directly rather than approximately.
- Implemented `launchd.py`: `build_plist`/`write_plist` (pure, file-only,
  idempotent by construction via `plistlib.dumps`, never touch the running
  `launchd`) versus `bootstrap`/`bootout`/`is_loaded` (real `launchctl`
  subprocess calls, kept in separate functions on purpose). `StartInterval`
  is always present (the roadmap's "reliable fallback to folder events");
  `WatchPaths` is added only for `schedule_mode == "monitoring"`.
  Coalescing/overlap prevention is *not* reimplemented here — it's already
  handled at the application layer by `io_utils.ScanLock`
  (`scheduling.run_scan`), which every `launchd`-triggered invocation goes
  through regardless of what triggered it.
- Extended `diagnostics.py` from its Phase 3/4-era single stub into
  `run_doctor`: `check_recordings_access` (now real — the FDA-EPERM
  distinction it always existed to make), `check_archive_root_writable`
  (walks up to the nearest existing ancestor and checks `os.access`; never
  creates anything), `check_config`, `check_state` (reports a corrupt
  `state.json` as self-healing, per Phase 6's `reconcile_with_archive`
  fallback, not as fatal), `check_scheduler` (via `launchd.is_loaded`,
  tri-state: loaded/not-loaded/unknown if `launchctl` itself is
  unavailable), and `check_pending_work` (needs_attention/conflict counts
  from `state.json`). Found and fixed a real design flaw while building
  this: an early draft of `run_doctor` fell back to `config.Config()`'s
  real global defaults when `config.json` was invalid, which would have
  silently checked the *wrong* folder if the corrupt config had been
  hiding a customized `recordings_source` — changed to skip those two
  checks with an explicit "skipped (config invalid)" result instead of
  guessing.
- Added `scheduling.run_scan`'s `force` parameter — Phase 7's "full
  rescan," distinct from Phase 6's `reconcile_with_archive` ("explicit
  full reconciliation," rebuilds state-only bookkeeping from the archive,
  no re-extraction). `force=True` bypasses the stable-status skip *and*
  any retry backoff in progress for `UNCHANGED` candidates, re-running
  extraction regardless — `write_archive_entry`'s own existing conflict
  detection still catches a genuine mismatch as `conflict`, so `force`
  only decides whether the attempt happens, never what happens once it
  does.
- Rewrote `cli.py` with the full command surface: `scan` (now with
  `--force`), `status` (per-status counts, last-scan summary, a
  needs_attention/conflict "inbox" listing — the roadmap's explicit
  wording), `doctor` (aggregates `run_doctor`, `[OK]`/`[FAIL]` per check),
  `retry` (`--id` or `--all`, mutually exclusive), `acknowledge`,
  `reconcile` (exposes `scheduling.reconcile_with_archive`), `verify`
  (read-only `archive.inspect_archive` report), and `setup` (preview,
  confirm-or-cancel unless `--yes`, writes `config.json` +
  `launchd`'s plist file unconditionally, but only ever calls
  `launchd.bootstrap` — a real, persistent system registration — behind
  `--enable-now` *and* a further confirmation unless `--yes` is also
  given).
- **Never invoked a real `launchctl` command against this machine while
  building/testing this phase** — every test that touches `launchd.py`
  mocks `subprocess.run` (or the higher-level `launchd.bootstrap`
  function directly), and every test that touches plist *file* writing
  (safe, inert) redirects `Path.home()` into `tmp_path` first so nothing
  ever lands in the real `~/Library/LaunchAgents`. Actually registering
  the automation on a real Mac is Phase 9's job, same as every other
  phase's real-environment deferral.
- 182 tests total (up from 126 at the end of Phase 6): 7 new in
  `test_config.py`, more in `test_scheduling.py` (import-mode filtering
  ×4, `force` ×1), and three new files —
  `tests/test_setup.py` (13), `tests/test_launchd.py` (10),
  `tests/test_diagnostics.py` (17) — plus `test_cli.py` rewritten and
  expanded (16, including a concurrent-scan/`ScanLock` test proving the
  "duplicate events... do not cause duplicate processing" exit criterion
  directly). `ruff check`/`ruff format --check` clean.
- Caught and fixed two real test-safety near-misses while writing tests
  (both before they ever ran, per this project's privacy invariants):
  `test_setup.py`'s early draft called `build_setup_plan()` with no
  explicit `recordings_source` in a few validation-only tests, which
  would have scanned the real default Voice Memos folder on whatever
  machine runs the suite in the "all"/"date" mode cases; and
  `test_diagnostics.py`'s corrupt-config test would have hit the same
  real-default path if `run_doctor` had kept the guess-the-default
  fallback described above (fixing the design flaw fixed the test hazard
  at the same time, not just worked around it).

- **Closed the interactive-wizard gap found during real Phase 9 usage
  (2026-09-10):** `setup` now genuinely prompts — in `cli.py`'s
  `_cmd_setup`, not `setup.py` (which stays side-effect-free per its own
  docstring) — for recordings source, archive destination, import mode
  (+ date if `date`), schedule mode, and scan interval, whenever the
  corresponding `--flag` is omitted. Each prompt shows a default the user
  can accept with Enter, and an invalid choice/date re-prompts rather than
  failing. `--yes` means fully non-interactive (per this session's design
  call, since a scripted/CI `setup --yes` must never block on stdin): it
  skips *all* prompting, field-level and the final confirmation alike, and
  fills anything not given via flag from the same source prompts would
  have defaulted to.
  - **"Seed from existing config" implemented:** `_cmd_setup` calls
    `config.load_config(args.config)` first (already returns `Config()`
    package defaults when no file exists yet, for free) and uses that as
    every prompt's/every `--yes`-path fallback's default — never the
    package's hardcoded `DEFAULT_*` constants directly. Verified live:
    re-running `setup` and accepting every prompt's default except
    `scan_interval_seconds` (a real answer) changed only that field and
    left the rest (including a non-default `schedule_mode` from the prior
    run) untouched. A corrupt existing `config.json` doesn't block
    re-running setup — it's reported as a warning to stderr and treated
    like no config existed, since the user is about to interactively
    confirm every value anyway.
  - Argparse's `--import-mode`/`--schedule-mode`/`--scan-interval` lost
    their `default=config.DEFAULT_*` (now bare `None`) so an omitted flag
    is distinguishable from an explicit choice; `choices=` still validates
    a value actually given.
  - Tests: `test_setup_declined_without_yes_writes_nothing` now supplies
    every value flag explicitly (it was relying on defaults for
    archive-root/import-mode/schedule-mode/scan-interval, which would
    otherwise now hit new prompts an "always answer n" mocked `input`
    can't safely satisfy — an unvalidated `"n"` for `import_mode` would
    have looped forever asking to re-enter a valid choice; caught this by
    actually running the suite, not just reasoning about it). Three new
    tests added: defaults shown with no existing config are the package
    defaults; an invalid choice/date re-prompts before succeeding; a
    second `setup` run seeds every prompt's default from the first run's
    committed `config.json`. 196 tests total (up from 193), `ruff
    check`/`ruff format --check` clean.
  - Manually smoke-tested end-to-end under a fake `HOME` (never the real
    one) for both the fresh-install and reconfigure-one-setting flows;
    caught and immediately cleaned up one real side effect during ad hoc
    testing before switching to the fake-`HOME` approach — an early manual
    check (before adding the `HOME` override) wrote a real, unregistered
    plist to this machine's actual `~/Library/LaunchAgents/`. It was never
    loaded into `launchd` (confirmed via `launchctl list`) and was deleted
    immediately.

**Not done yet — next action:**

- None of this has been exercised against a real `launchd` install, a
  real first-run `setup` on this machine, or real Voice Memos recordings
  — only synthetic fixtures and mocked `subprocess`/`Path.home()` calls.
  Phase 9's job, consistent with every other phase's synthetic-test
  acceptance so far. Actually running `setup --enable-now` for real is a
  deliberate, separate, explicit decision for whoever does that
  verification — not something to do casually while testing.
- Real-terminal testing of `setup`'s `input()` prompts is now done for the
  settings menu and the confirm-or-cancel step (2026-09-12 session log
  entry above) — prompt wording, invalid-input reprompting, and Ctrl-C
  mid-prompt all behave correctly in an actual TTY, not just under
  monkeypatched `builtins.input`. The one prompt still untested in a real
  terminal is the separate "Enable background automation now?"
  confirmation (`--enable-now` without `--yes`), since this pass didn't use
  `--enable-now`.
- `doctor`'s `check_archive_root_writable` only checks `os.access`, which
  can disagree with actual write success in edge cases (e.g. some network
  filesystems, ACLs `os.access` doesn't fully model) — accepted as a
  reasonable diagnostic approximation, not a guarantee, consistent with
  diagnostics being advisory rather than authoritative.
- The `verify` command's malformed/orphaned output goes to stderr with an
  exit code, but there's no way yet to *act* on a malformed archive entry
  from the CLI (no delete/repair command) — matches the project's
  never-delete invariant (Phase 5), so this is likely intentional rather
  than a gap, but worth a human's judgment call if it ever comes up.

## Scope and decisions to validate

- [x] Offer command-line source selection and an archive-destination
      prompt defaulting to `~/Documents/Voice Memo Archive/`, all/date/
      new-only initial import, a candidate-count preview, cancellation/
      resume, monitoring or scheduled mode, and supported scan intervals.
      Setup must disclose that a Documents destination may be iCloud
      Drive-synced according to the user's macOS settings. _`setup.py` +
      `cli.py`'s `setup` subcommand implement all of this. As of 2026-09-12,
      the interactive form is a single menu (`_edit_setup_menu`) showing
      every setting and its current value at once — resolved from `--flag`,
      else the current `config.json`, else the package default — editable
      by number in any order, repeating until Enter is pressed; picking
      `import_mode` `date` immediately asks for `import_since`. Then the
      existing candidate-count preview and a final y/N confirmation, same
      as before. `--flag`s remain a full non-interactive override path via
      `--yes`, unchanged. "Resume" is idempotent re-running of `setup`
      (tested), not a distinct resume path — as originally written._
- [x] Define idempotent user-level `launchd` installation. Treat periodic
      scan as the reliable fallback to folder events; coalesce repeated
      triggers and prevent overlap. _`launchd.py`; overlap prevention is
      `io_utils.ScanLock`, already built (Phase 2) and already exercised
      by every `run_scan` call regardless of trigger source._
- [x] Provide a command-line surface only: setup, scan now, status,
      targeted and bulk retry, acknowledgment, full rescan, archive
      verification, and `doctor` diagnostics. Background runs remain quiet
      during ordinary pending and retry states; `status` is the
      user-visible inbox for unresolved work. _All eight implemented in
      `cli.py`. "Background runs remain quiet": a normal scan's stdout is
      just a one-line count summary; `status` is the only place
      needs_attention/conflict records are listed out._
- [x] Ensure diagnostics check scheduler state, permission status, source
      availability, configuration, pending retries, conflicts, and
      needs-attention records without exposing transcript text.
      _`diagnostics.run_doctor`'s six checks. No check ever reads
      transcript content — `RecordingState` never stores it in the first
      place, so this is true by construction, not by careful redaction._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 7:

- [x] Users see what initial import will consider before it begins.
      _`build_setup_plan`'s `candidate_preview_count`, printed by `setup`
      before the confirm-or-cancel prompt; tested directly at the CLI
      level (`test_setup_with_yes_writes_config_and_plist_without_enabling`
      asserts the exact preview line appears)._
- [x] Cancellation, restart, duplicate events, and login/restart behavior
      do not cause duplicate processing. _Cancellation: declining setup's
      prompt writes nothing (tested). Restart (re-running setup): the
      config write is idempotent (tested in `test_setup.py`). Duplicate
      events (e.g. `WatchPaths` and `StartInterval` firing close
      together): a concurrent `scan` invocation is refused cleanly by the
      existing `ScanLock`, not raced — tested directly at the CLI level.
      Login/restart (`RunAtLoad: true`): relies on the same idempotent
      `run_scan`/`ScanLock` machinery every other trigger does; no
      special-cased "first run after login" logic exists or is needed._
- [x] Status and doctor provide actionable, privacy-safe recovery
      guidance. _`status` names the specific recording ID, source
      filename, reason, and attempt count for anything needing attention;
      `doctor` names which check failed and why, including the FDA-denial
      case's specific System Settings pointer. Privacy-safe by
      construction, not by redaction discipline alone — no code path in
      either command ever has transcript text in hand to begin with._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-09: Created this task file. No implementation yet.
- 2026-09-09 (same day, continued): Implemented the full phase — Phase 7
  config fields, the import-mode cutoff filter, `setup.py`, `launchd.py`,
  the extended `diagnostics.py`, `scheduling.run_scan`'s `force` param,
  and the full `cli.py` command surface. Found and fixed a config
  validation gap (malformed `import_since`/`setup_completed_at` crashing
  a scan instead of failing at load) and a `run_doctor` design flaw
  (guessing real defaults on a corrupt config instead of skipping).
  Caught two test-safety near-misses (real recordings-folder scans,
  real `~/Library/LaunchAgents` writes) before they ever ran. Outcome:
  182/182 tests pass; `ruff check`/`ruff format --check` clean.
- 2026-09-10: Started real Phase 9 verification (`voice-memo-archive
  doctor` against this machine's real Voice Memos folder — Full Disk
  Access already worked, no `config.json` existed yet). Before running
  `setup` for real, the user pushed back on the flag-only UX and asked
  for a genuine interactive wizard, editable later by re-running `setup`
  with the current config as each prompt's default. Recorded as a gap
  above (reopened the first Scope checkbox rather than leaving it
  checked) and explicitly deferred, on the user's own direction, so
  real-environment testing could continue with the existing flag-driven
  `setup` in the meantime. No code changed this entry.
- 2026-09-10 (same day, continued): Built the deferred interactive wizard.
  `_cmd_setup` now prompts for any value not given via flag, seeded from
  the current `config.json` (or package defaults with none yet); `--yes`
  skips all prompting including the final confirmation, for scripted use.
  Updated one existing test that relied on unflagged defaults (would have
  hung on the new prompts under its "always answer n" mocked `input`) and
  added three new tests for the prompt/reprompt/reconfigure-seeding
  behavior. Manually verified live under a fake `HOME`; also caught and
  cleaned up a real (never-loaded) `~/Library/LaunchAgents` plist written
  by one early manual check before switching to the fake-`HOME` approach.
  Outcome: 196/196 tests pass; `ruff check`/`ruff format --check` clean;
  first Scope checkbox re-closed.
- 2026-09-12: Replaced the sequential interactive wizard with a
  single-screen menu, per the user's explicit request during a Phase 9
  status check-in (not a defect report — the user found the fixed-order
  prompt sequence harder to review at a glance than a menu showing
  everything at once). Added `_format_setup_menu`/`_ensure_import_since`/
  `_edit_setup_menu` to `cli.py`; `_cmd_setup` now resolves all six
  settings' starting values up front (flag, else current `config.json`,
  else package default — the same merge `--yes` already used), then, when
  not `--yes`, hands that to the menu loop before building the setup plan.
  Rewrote the four interactive-flow tests in `test_cli.py` around the new
  input sequence (menu selection digits instead of one input per field) and
  added a dedicated by-number-edit test. Manually smoke-tested the actual
  printed menu output via piped stdin under a fake `HOME` (not a real
  interactive terminal — that gap already existed before this change; see
  "Not done yet" above). Outcome: 196/196 tests pass; `ruff check`/`ruff
  format --check` clean.
- 2026-09-12 (same day, continued): Did the real-terminal verification the
  prior entry deferred, live with the user against a scratch
  `/tmp/vma-terminal-test/` tree (never the real Voice Memos folder or
  config). Confirmed in an actual TTY: the menu prints and edits correctly;
  an invalid menu digit and an invalid `import_mode` value both reprompt
  correctly; choosing `date` immediately asks for `import_since`; declining
  the final confirm writes nothing; Ctrl-C at a prompt exits cleanly (no
  traceback). **Found and fixed a real bug in the process, pre-dating the
  menu redesign:** an unreadable/missing `recordings_source` (the user's
  first attempt, before creating the scratch folder) crashed with a raw
  Python traceback — `build_setup_plan`'s candidate-count preview calls
  `discovery.scan`, which raises `ArchiveError`, but `_cmd_setup` only
  caught `ValueError` around that call. Added an `ArchiveError` catch
  alongside it (`cli.py`), printing the same clean `[source_unreadable] ...`
  message `scan` itself already gives, plus a regression test
  (`test_setup_fails_cleanly_when_recordings_source_does_not_exist`).
  Outcome: 197/197 tests pass; `ruff check`/`ruff format --check` clean;
  no interactive-terminal testing gap remains open for this phase.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 7
here, per `AGENTS.md`'s working method._

- 2026-09-09: `setup` writes the `launchd` plist file unconditionally but
  requires `--enable-now` plus a confirmation (or `--yes`) before actually
  calling `launchd.bootstrap` to register it with the running `launchd`.
  The roadmap's "idempotent user-level launchd installation" line could be
  read as expecting `setup` alone to fully activate automation. This is a
  deliberate, more cautious interpretation — see `cli.py`'s module
  docstring and this file's earlier discussion — not a rejection of the
  feature; the capability is fully implemented and one flag away.
- 2026-09-10: `--yes` was implemented to mean "fully non-interactive,"
  skipping every field-level prompt as well as the final confirmation
  (falling back to the current config's value for anything not flagged),
  rather than only skipping the confirmation and still prompting for any
  missing field. The roadmap doesn't specify this distinction; treating
  `--yes` as "no stdin interaction at all" was judged necessary for
  scripted/CI use of `setup --yes` to stay non-blocking, and matches how
  this project's own tests already used `--yes` together with explicit
  flags for determinism before this session.
