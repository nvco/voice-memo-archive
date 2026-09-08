# Foundation and test harness

Focused task plan for Phase 2 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Phase 1 (`tasks/005-platform-feasibility-and-data-contract.md`) produced
  the draft extraction result contract and support matrix this phase builds
  on. Its remaining gaps are documented there as deprioritized, not
  blocking.
- Chose Python as the implementation language/toolchain (recorded in
  `tasks/000-initial-build.md`'s Plan history). No packaging decision yet —
  Phase 8 must choose how to bundle a Python runtime so a clean macOS
  account doesn't need one preinstalled.
- Package layout and tooling settled: `src/voice_memo_archive/` (setuptools,
  `uv`-managed `.venv`), `pytest` for tests, `ruff` for lint+format. Dev
  setup documented in `AGENTS.md`'s new "Development setup" section and
  verified reproducible from a clean `.venv` rebuild this session.
- Module boundaries created, each owned by its future phase and stubbed
  with `NotImplementedError` where unimplemented: `config.py`, `state.py`,
  `schema.py` (generic migration), `errors.py`, `paths.py`, `io_utils.py`
  (atomic write + scan lock), `yaml_meta.py`, `discovery.py`,
  `extraction.py`, `archive.py`, `scheduling.py`, `diagnostics.py`, and a
  thin `cli.py` that only calls into `scheduling`/`diagnostics`.
- `config.json`/`state.json` schemas implemented at version 1 with a
  tested generic migration chain (`schema.py`, exercised directly with a
  synthetic multi-step migration in `test_schema.py` since neither real
  schema has a prior version yet to migrate from) and tested
  missing-file/corrupt-file recovery behavior.
- Atomic writes and a stale-lock-reclaiming `ScanLock` implemented and
  tested with no CLI/launchd involvement (`test_io_utils.py`), satisfying
  the exit criterion directly.
- Error taxonomy (`ErrorCategory` + `ArchiveError`) implemented with a
  safe-by-default `message`/opt-in `detail` split so logging a caught
  error never includes transcript text or a raw path by construction
  (`paths.redact_home_path` used wherever a path enters `detail`).
- Synthetic-vs-golden fixture directories created
  (`tests/fixtures/synthetic/`, `tests/fixtures/golden/`) with README files
  documenting the distinction and construction rules, establishing the
  mechanism Phase 2's scope calls for.
- 43 tests passing; `ruff check .` and `ruff format --check .` clean.

**Not done yet — next action:**

- No actual synthetic ISO-BMFF/QuickTime *byte* fixtures exist yet — only
  the directory/README mechanism. Building them now would have no
  consumer (Phase 4's atom parser doesn't exist yet); left for Phase 4 to
  add alongside the parser they test. See the unchecked scope item below.
- Nothing else outstanding for this phase's own scope; Phase 3 can begin
  once its own focused task file is created.

## Scope and decisions to validate

_Carried over verbatim from `tasks/000-initial-build.md` Phase 2, plus this
file records how each is actually approached as work proceeds._

- [x] Separate configuration, operational state, discovery, extraction,
      archiving, scheduling, and diagnostics so no command-interface choice
      defines the core workflow. _Modules created per the "Done" list
      above; `cli.py` only calls into them._
- [x] Version `config.json`, `state.json`, and generated YAML metadata.
      Validate and migrate every schema; settings must survive state reset
      or reconstruction. _`schema.py` + `config.py`/`state.py`/`yaml_meta.py`,
      tested in `test_schema.py`/`test_config.py`/`test_state.py`/
      `test_yaml_meta.py`._
- [x] Define filename/path parsing, date and timezone utilities, structured
      error categories, scan locking, and atomic-write behavior.
      `paths.py`, `errors.py`, `io_utils.py`, tested.
- [ ] Build synthetic ISO-BMFF/QuickTime and filesystem fixtures alongside a
      separate redacted-golden-fixture mechanism. _Directory/README
      mechanism exists (`tests/fixtures/synthetic/`,
      `tests/fixtures/golden/`); actual byte-level fixtures deferred to
      Phase 4, which is what will consume them. Left unchecked since the
      fixtures themselves don't exist yet._
- [x] Provide offline test, lint, and formatting commands that never
      require real Voice Memos data. _`pytest`, `ruff check`,
      `ruff format` — verified working from a from-scratch `.venv` rebuild
      this session, no real data involved._
- [x] Ensure error reports and logs do not contain transcript text. Treat
      transcript content, source names, and absolute paths as sensitive
      diagnostic data by default. _`ArchiveError`'s safe `message` vs.
      opt-in `detail` split, tested in `test_errors.py`; no logging
      subsystem exists yet to wire this into (out of Phase 2's scope), but
      the structural guarantee is in place and tested for what does exist._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 2:

- [x] A fresh checkout runs focused tests using only synthetic or redacted
      fixtures. _Verified this session: `rm -rf .venv`, rebuilt via the
      exact commands now documented in `AGENTS.md`'s "Development setup",
      ran `pytest`/`ruff check`/`ruff format --check` clean._
- [x] State, configuration, and output metadata schemas have explicit
      versions and tested migration/recovery behavior.
- [x] The scan lock and error taxonomy are testable independently of the
      CLI or `launchd`. _`test_io_utils.py`/`test_errors.py` exercise both
      directly with no CLI or launchd involved._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-08: Set up the Python package (`src/voice_memo_archive/`,
  `pyproject.toml`, `uv`-managed `.venv`), implemented `errors.py`,
  `paths.py`, `io_utils.py`, `schema.py`, `config.py`, `state.py`,
  `yaml_meta.py`, stub modules for `discovery`/`extraction`/`archive`/
  `scheduling`/`diagnostics`, and a thin `cli.py`. Wrote 43 tests across
  all of the above; added `AGENTS.md`'s "Development setup" section.
  Outcome: `pytest` (43 passed), `ruff check .`, and `ruff format --check .`
  all clean, verified reproducible from a from-scratch `.venv` rebuild.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 2
here, per `AGENTS.md`'s working method._

(none yet)
