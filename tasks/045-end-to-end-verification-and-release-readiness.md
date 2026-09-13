# End-to-end verification and release readiness

Focused task plan for Phase 9 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

Per the 2026-09-09 decision recorded in
`tasks/040-packaging-permissions-and-privacy.md`, this project is
personal-use only for now — "release readiness" in this phase's name means
"ready for the user's own confident daily use," not a public release.

## Status

_Last updated: 2026-09-13. Read this section first in a new session to see
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
- Ran item 2 (real verification) against this machine's actual Voice
  Memos folder, guided live with the user:
  - `doctor` confirmed Full Disk Access already worked for the shell that
    ran it, and `archive_root` was writable — no permission-grant walk
    needed this time.
  - `setup --import-mode date --import-since 2026-09-01 --yes` (chosen by
    the user; no `--enable-now`, so automation was prepared but not
    registered) correctly previewed **21 recordings** before writing
    anything, matching an independent manual count.
  - `scan` processed real data: **16 processed, 3 pending, 2
    skipped_no_transcript**. `inspect_archive` confirmed all 16 written
    files are valid (0 malformed, 0 orphaned). Confirmed both formats
    genuinely reached `processed` (not just present in the source
    folder): **6 real `.m4a` + 10 real `.qta`**, each with non-empty,
    correctly-metadata'd archive entries (`recorded_at` with a real
    timezone offset, correct `locale`, correct `source_format`) —
    satisfies this phase's first exit criterion directly, not just
    plausibly.
  - A second `scan` correctly resolved the 3 `pending` (empty-on-first-
    look) recordings to `skipped_empty` — the two-scan stability
    confirmation working exactly as designed against real, unmodified
    source files. Archive stayed at exactly 16 files (no duplication on
    a repeated/"service restart"-like scan).
  - `scan --force` (never previously run against a real machine) correctly
    re-verified all 21 candidates: the 3 `skipped_empty` reset to
    `pending` (force doesn't carry over prior confirmation state — a
    fresh verification cycle, by design) with **no duplication** (still
    16 archive files). This is the first real-environment proof of the
    "full rescan" feature.
  - `doctor` correctly reported `scheduler: not loaded` as a `FAIL` —
    correct, since automation was deliberately not enabled; not a bug.
  - Together this satisfies "expected non-success states are visible and
    repairable": `status`/`doctor` both surfaced `skipped_no_transcript`/
    `skipped_empty` clearly, and the empty ones demonstrably *did* resolve
    on a follow-up scan.
  - **Real-data finding, resolved as not-a-bug:** the user noticed the
    archived transcript is one continuous block of text, while the Voice
    Memos app displays it with paragraph breaks. Investigated directly
    against the real container (full box-tree dump, not just the one
    metadata entry this project already extracts): confirmed no
    paragraph/newline/pause data exists anywhere in the file — the only
    other metadata block present is the recording's title + UUID, nothing
    transcript-related. Corroborated independently via web research: this
    matches widely-reported behavior of Apple's own "copy transcript"
    feature. Conclusion: the archive is a faithful, complete copy of
    everything Apple actually stores; the paragraph rendering is
    display-only and doesn't exist in the source data at all, so there is
    nothing to more-faithfully preserve. **Side finding kept for later,
    not acted on now:** the recording's title (e.g. "New Recording 6") is
    present in the container and is not currently extracted/archived —
    purely factual, could be added to `yaml_meta.REQUIRED_FIELDS` later;
    not requested yet.
  - Manual verification matrix items not covered by this run: delayed
    iCloud download, an explicit permission-denial scenario (FDA already
    worked, so nothing to deny), and `acknowledge`/`needs_attention`
    (nothing reached that status in this batch — no transient failures
    occurred). Accepted as untested for now; nothing in this batch
    exercised those paths, and forcing a permission denial would mean
    revoking the user's own real Full Disk Access grant, which wasn't
    judged worth the disruption for this pass.
- **Found during this real-recording testing, not code — recorded in
  `tasks/035-...md`, not here:** `setup` is flag-driven, not the
  interactive prompt wizard the roadmap actually described. Deferred on
  the user's explicit direction until after this phase.
- **A new, out-of-roadmap idea surfaced, deliberately deferred, then
  dropped:** a sample "summarize the archive with your own AI tool"
  skill, recorded in `tasks/future-ai-summary-skill.md` (no phase
  number). Never started, and on 2026-09-13 the user decided it wasn't
  actually needed — the file was removed rather than left sitting as a
  stale, unstarted idea.

**Not done yet — next action:**

- A few manual-verification-matrix items genuinely weren't exercised by
  this real batch (see "Done" above for exactly which, and why each was
  reasonable to skip for now): delayed iCloud download, an explicit
  permission-denial scenario, and `acknowledge`/`needs_attention` (no
  transient failures occurred in this batch — nothing to acknowledge).
  Pick these up naturally the next time a real recording happens to
  exercise one (e.g., a future needs_attention record is the natural
  moment to test `acknowledge` for real), rather than manufacturing an
  artificial failure just to test the path.
- The setup-wizard gap is tracked elsewhere (`tasks/035-...md`); the
  AI-summary-skill idea is closed (see "Done" above, dropped 2026-09-13)
  — nothing to duplicate here.
- "Convert each verified defect or important gap into a new numbered task
  plan before release" — the one real gap found (the setup wizard) was
  recorded in the *existing* Phase 7 file rather than a new numbered one,
  since it's a gap in something Phase 7 already built, not a new phase.
  The AI-summary-skill idea got its own (deliberately unnumbered) task
  file at the time, satisfying "recorded before treating [Phase 9] as
  complete" — since removed entirely (2026-09-13) once the user decided
  the idea wasn't wanted, rather than left as permanent dead weight.

**Phase 9 is now closed** (2026-09-13) — every exit criterion below is
satisfied; see the session log for the two remaining items closed that
day (this file's earlier "Not done yet" verification-matrix gaps are
still genuinely open, deliberately, per the note above — they don't block
closing the phase, matching how this file already treated them since
2026-09-10).

## Scope and decisions to validate

- [x] Maintain a manual verification matrix for macOS, source-device
      transcript availability, language/region, real synced mono, stereo,
      and spatial `.m4a` and `.qta`, delayed download, missing transcript,
      empty source, source change, permission denial, service restart,
      acknowledgment, and state recovery. Real samples remain local and
      are never committed. _Covered against real data: real `.m4a`
      (6 processed) and real `.qta` (10 processed), missing transcript
      (`skipped_no_transcript`, 2), empty source (`skipped_empty`, 3,
      confirmed across two real scans), service restart (repeated scan,
      no duplication), and `--force` full-rescan (also new-to-real-data
      this session). Not covered: delayed download, permission denial,
      acknowledgment, source change — see "Not done yet" for why each was
      reasonably skipped this pass rather than manufactured artificially._
- [x] Run the full automated suite, package smoke tests, clean-install
      test, and repository audit for private fixtures and unintended
      network dependencies.
- [x] Review setup, normal workflow, recovery, privacy, support matrix,
      limitations, and removal documentation. _`AGENTS.md`'s developer-
      facing setup docs are confirmed accurate (the clean-install smoke
      test above exercises them directly). `README.md` was substantially
      rewritten across 2026-09-12/13 (Installation's `.venv`/`PATH`
      requirement made unmissable, Setup, Everyday use, the two supported
      usage modes, Privacy, Uninstalling, Known limitations) and is now
      accurate, complete, and privacy-safe for the distribution form
      actually decided on (`tasks/040-...md`: source install, shareable
      via GitHub) — see the 2026-09-13 exit-criterion note below for why
      this closes the line rather than deferring it further._
- [x] Convert each verified defect or important gap into a new numbered
      task plan before release; do not hide it in release notes. _The
      setup-wizard gap went into the existing Phase 7 file (a gap in
      something already built there, not new scope); the AI-summary-skill
      idea got its own new file. See "Not done yet" for why neither is
      literally a new *numbered* file and why that's still faithful to
      this line's intent._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 9:

- [x] At least one real synced `.m4a` and one real synced `.qta` complete
      the archive flow with their visible Apple transcript preserved.
      _6 real `.m4a` + 10 real `.qta` reached `processed`, each verified
      to have non-empty transcript content and correct metadata._
- [x] Expected non-success states are visible and repairable. _`status`/
      `doctor` surfaced `skipped_no_transcript` and (pre-confirmation)
      `pending` clearly; the `pending` recordings demonstrably resolved
      (repaired themselves) to `skipped_empty` on the next real scan. A
      real `needs_attention` record specifically didn't occur in this
      batch — nothing failed — so that exact status is still only
      test-covered, not real-data-covered; noted in "Not done yet"._
- [x] No personal audio, transcript, title, identifier, or raw private
      note is tracked in Git. _Confirmed directly by the repository audit
      above: no tracked `.m4a`/`.qta`/audio file of any kind, no tracked
      real filesystem path, `.local/` untracked and unreferenced except
      by documentation describing the rule itself._
- [x] Release documentation and known limitations are ready for public
      review. _2026-09-13: closed, on the user's explicit "whatever you
      think" direction. This was left open reasoning "not relevant while
      personal-use only," but that framing was already outdated —
      `tasks/040-...md`'s 2026-09-09 decision settled on a real,
      shareable distribution form (source install via GitHub clone), not
      pure private use. Holding this criterion open waiting for a
      signed/notarized general-audience release would be holding it to a
      bar this project never targeted (see `README.md`'s own "no
      signed... distribution... not a double-click installer for a
      general audience" line). Judged against the form actually decided
      on: `README.md` now covers requirements, installation (including
      the `.venv`/`PATH` gotcha, made prominent after a real user hit
      it), setup, everyday use, both supported usage modes, privacy
      guarantees (each one backed by an automated test, not just
      asserted), uninstalling, and known limitations — accurate,
      complete, and contains no private data. Good enough to point a
      stranger at._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-09: Created this task file. No implementation yet.
- 2026-09-09 (same day, continued): Ran the automatable subset —
  automated suite, repository/private-material audit, network-dependency
  audit, and a from-scratch clean-install smoke test through the real
  console-script entry point. All passed; no findings. The remaining
  scope needs the user to run the tool for real against real recordings,
  which this session deliberately did not do on its own initiative.
- 2026-09-10: Ran real verification live with the user against this
  machine's actual Voice Memos folder: `doctor` (FDA already worked),
  `setup` (date cutoff 2026-09-01, chosen by the user; automation
  prepared but not enabled), `scan` (16 processed/3 pending/2
  skipped_no_transcript; both `.m4a` and `.qta` represented), a second
  `scan` (empty-transcript confirmation resolved correctly, no
  duplication), and `scan --force` (full rescan against real data for
  the first time, correct reset-and-reverify behavior, no duplication).
  Investigated and resolved a real user-noticed discrepancy (archived
  transcript is unparagraphed while the Voice Memos app shows paragraphs)
  by decoding the full real file structure directly and corroborating
  with web research — concluded the archive is faithful and there is no
  paragraph data in the source to preserve. Recorded a setup-UX gap in
  `tasks/035-...md` and a new AI-summary-skill idea in
  `tasks/future-ai-summary-skill.md`, both deliberately deferred per the
  user's direction. Outcome: all real-data checks passed; no code
  changes this session (verification and documentation only).
- 2026-09-13: Closed out the two remaining open items from this file.
  User decided the AI-summary-skill idea wasn't actually needed;
  `tasks/future-ai-summary-skill.md` was removed entirely (unstarted, no
  code affected). Separately, asked to close the public-review
  documentation question with "whatever you think" — judged it already
  satisfied for the distribution form actually decided in
  `tasks/040-...md` (source install, not a signed general-audience
  release) given `README.md`'s current state (Requirements, Installation
  with the `.venv`/`PATH` gotcha made prominent, Setup, Everyday use, the
  two supported usage modes, Privacy, Uninstalling, Known limitations —
  all accurate, complete, no private data). Checked off both remaining
  exit criteria; **Phase 9 is now fully closed.** No code changes.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 9
here, per `AGENTS.md`'s working method._

- 2026-09-10: A handful of manual-verification-matrix items (delayed
  download, permission denial, acknowledgment, source change) were not
  exercised against real data this pass, because nothing in this
  particular real batch happened to trigger them and manufacturing an
  artificial failure (e.g. revoking real Full Disk Access) wasn't judged
  worth the disruption. Not a silent gap — named explicitly here and in
  the Scope checkboxes above, to be picked up naturally when a real
  occurrence arises rather than forced.
