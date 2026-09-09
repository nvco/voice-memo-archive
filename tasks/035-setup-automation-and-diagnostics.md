# Setup, automation, and diagnostics

Focused task plan for Phase 7 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-09. Read this section first in a new session to see
what's done and what to do next._

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

**Not done yet — next action:**

- None of this has been exercised against a real `launchd` install, a
  real first-run `setup` on this machine, or real Voice Memos recordings
  — only synthetic fixtures and mocked `subprocess`/`Path.home()` calls.
  Phase 9's job, consistent with every other phase's synthetic-test
  acceptance so far. Actually running `setup --enable-now` for real is a
  deliberate, separate, explicit decision for whoever does that
  verification — not something to do casually while testing.
- No interactive-terminal testing of the `input()` prompts in `setup`
  (confirm-or-cancel, enable-now confirmation) beyond monkeypatching
  `builtins.input` — real terminal UX (prompt wording, Ctrl-C handling
  mid-prompt) is untested.
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
      `cli.py`'s `setup` subcommand. "Resume" specifically: re-running
      `setup` is idempotent (tested) rather than needing a distinct resume
      path — there's no partial/interrupted setup state to resume from,
      since `commit_setup` is a single atomic `config.json` write._
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
