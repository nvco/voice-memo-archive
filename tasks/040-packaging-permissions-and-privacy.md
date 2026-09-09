# Packaging, permissions, and privacy

Focused task plan for Phase 8 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-09. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Implemented item 1 (the pure-engineering subset):
  - `cli.py`'s new `uninstall` subcommand: `launchd.bootout()` (safe/
    no-op if nothing was ever registered) plus deleting the plist file if
    present; `config.json`/`state.json` are only removed with an explicit
    `--purge-config` flag (off by default — they're settings/bookkeeping,
    not the "service" itself). No code path in `_cmd_uninstall` reads
    `archive_root` at all — the "never delete the archive" guarantee is
    structural, not a redaction to get right. Tested directly, including
    that a real archived `.md` file is provably still present and
    non-empty afterward.
  - `tests/test_privacy_claims.py` (new): proves, at the `cli.py` command
    level (not just `extraction.py`, which `test_extraction.py` already
    covered), that `scan`/`status`/`doctor`/`verify`/`reconcile`/`setup`/
    `uninstall` never open a network socket (`socket.socket`/
    `socket.create_connection` monkeypatched to raise), and that a
    transcript containing a distinctive marker string never appears in
    any command's captured stdout/stderr — including after a real
    `processed` archive write, confirmed by also asserting the marker
    *is* present in the archived `.md` file itself, so the "absent from
    output" result is provably because output is clean, not because
    extraction silently failed and there was nothing to leak. Caught a
    real bug in an early draft of these tests while writing them: passing
    a single-element `runs_texts` to `mp4.make_transcript_json` without a
    matching single-element `time_ranges` produced a mismatched
    attribute-table length, which `extraction.py` correctly classifies as
    `incomplete`/`failed` — meaning the first draft's "no leak" assertions
    were trivially true (nothing was ever extracted to leak) rather than
    proving anything. Fixed by passing matching `time_ranges`.
  - 11 new tests total (3 `uninstall` in `test_cli.py`, 8 in the new
    `test_privacy_claims.py`); 193 tests total; `ruff check`/
    `ruff format --check` clean.
- Decided the distribution form: **source install from the cloned repo**
  (`git clone` + `pip install -e ".[dev]"`), not a signed/notarized `.app`
  or `.pkg`. No code signing or notarization is needed for this form at
  all — it isn't a signed macOS bundle. This was initially deferred (see
  the first two Session log entries below) on a "personal use only"
  answer, then revisited the same day once the user considered sharing
  the repo with others who'd install it themselves the same way.
  Concretely this means:
  - `requires-python = ">=3.11"` in `pyproject.toml` was already correct
    (confirmed by grep: `enum.StrEnum` and `datetime.UTC`, both added in
    3.11, are used throughout) and needed no change.
  - Added a `readme = "README.md"` field to `pyproject.toml` and wrote
    `README.md` — install steps (already proven correct by Phase 9's own
    clean-install smoke test, not just described), `setup`/everyday-use
    walkthrough, the privacy guarantees, `uninstall` behavior, and a
    known-limitations section. Re-ran the clean-install smoke test after
    the `pyproject.toml` change to confirm it didn't break the build.
  - **Named, not silently absorbed:** this distribution form does not
    satisfy the roadmap's literal "without a developer runtime" wording —
    `pip install` requires Python 3.11+ already present, which a
    completely bare Mac doesn't have. Per the user's explicit direction,
    this is documented as a normal prerequisite (`README.md`'s
    Requirements section) rather than treated as a gap to close with a
    future bundled/frozen build — that remains a real option later if the
    audience ever needs to be non-technical users, but is out of scope
    now.

**Not done yet — next action:**

- "Explain that an archive destination selected by a user may itself be
  cloud-synced; document local-storage, FileVault, backup, upgrade, and
  uninstall behavior honestly" — covered in `README.md`'s Privacy and
  Uninstalling sections at the level this project's actual distribution
  form needs. "Upgrade" specifically has no dedicated procedure yet
  beyond `git pull` + reinstall — worth a session's attention if/when
  this ever needs a real migration story (e.g. a config schema bump).

## Scope and decisions to validate

- [x] Choose the distribution form and package dependencies so users do
      not need a developer runtime. Document code signing and
      notarization requirements before public release. _Decided: source
      install (`git clone` + `pip install`), documented in `README.md`.
      No code signing/notarization applies to this form — named
      explicitly rather than silently declared "N/A". Does not satisfy
      the literal "without a developer runtime" wording (Python must
      already be present) — accepted deliberately, see "Done" above._
- [x] Validate Full Disk Access for the actual signed process. Diagnose
      missing access rather than reporting "no recordings." _There is no
      "signed process" in this distribution form — `diagnostics.check_recordings_access`
      (Phase 7) already explicitly distinguishes the FDA-EPERM case from
      a generic failure for whatever process runs the tool, which is the
      applicable form of this criterion now._
- [x] Make no telemetry, analytics, remote crash reporting, or network
      call part of the product. Test this claim rather than merely
      documenting it. _`tests/test_privacy_claims.py`, proven at the
      product (`cli.py`) level for every command._
- [x] Explain that an archive destination selected by a user may itself
      be cloud-synced; document local-storage, FileVault, backup, upgrade,
      and uninstall behavior honestly. _`README.md`'s Setup, Privacy, and
      Uninstalling sections. "Upgrade" is thin (`git pull` + reinstall,
      no real migration story yet) — noted in "Not done yet"._
- [x] Uninstalling the service must not delete the user's archive. Logs
      should omit transcript content and sensitive paths by default.
      _`cli.py`'s `uninstall`, and `tests/test_privacy_claims.py`'s
      output-redaction proofs._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 8:

- [x] A clean macOS account can install and run the distribution without
      a developer runtime. _Satisfied for the decided distribution form
      as: no Xcode, no Apple Developer Program, no signing/notarization
      required. Requires Python 3.11+ already present — a named,
      accepted limitation (see "Done" above), not silently glossed over.
      The actual clean-account install run is Phase 9's real-hardware
      job; the smoke test proves the *steps* work, not a truly bare
      machine._
- [x] Permission failures are accurately diagnosed. _`diagnostics.check_recordings_access`
      (Phase 7) already explicitly distinguishes the FDA-EPERM case from
      a generic failure._
- [x] Network denial and log-redaction checks pass. _`tests/test_privacy_claims.py`._
- [x] Public privacy, installation, upgrade, and uninstall documentation
      matches tested behavior. _`README.md`, grounded in what Phase 7-9's
      own tests and the clean-install smoke test actually verified —
      not aspirational._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-09: Created this task file. No implementation yet.
- 2026-09-09 (same day, continued): Implemented the pure-engineering
  subset — `cli.py`'s `uninstall` subcommand and
  `tests/test_privacy_claims.py`'s network-denial and log-redaction
  proofs. Raised the distribution-form/code-signing decision as an
  explicit question rather than guessing. Outcome: 193/193 tests pass;
  `ruff check`/`ruff format --check` clean.
- 2026-09-09 (same day, continued): Asked the user directly whether to
  decide the distribution form now or treat this as personal-use-only for
  now; answer was personal-use-only. Deferred the remaining Phase 8 scope
  and moved to Phase 9 (`tasks/045-...md`).
- 2026-09-09 (same day, continued): User reconsidered — the repo may be
  shared with others who'd install it themselves, so the distribution
  form does need deciding after all. Chose source install (`git clone` +
  `pip install`, "option 2" from the earlier question) on the user's
  explicit direction; confirmed `requires-python = ">=3.11"` was already
  correct (grep for `StrEnum`/`datetime.UTC` usage); added `README.md`
  and a `readme` field in `pyproject.toml`; re-ran the clean-install
  smoke test to confirm the `pyproject.toml` change didn't break the
  build. Outcome: 193/193 tests pass; `ruff check`/`ruff format --check`
  clean.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 8
here, per `AGENTS.md`'s working method._

- 2026-09-09: The decided distribution form (source install) does not
  satisfy the roadmap's literal "without a developer runtime" wording —
  Python 3.11+ must already be present. This is a deliberate, named
  acceptance on the user's explicit direction (see Session log), not a
  silent reinterpretation of the exit criterion: `README.md`'s
  Requirements section states the Python prerequisite plainly rather than
  implying a bare-metal install works.
