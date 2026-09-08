# Native transcript extraction and fidelity

Focused task plan for Phase 4 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- `extraction.py` implemented: a bounded ISO-BMFF/QuickTime atom walker
  (`_iter_boxes`/`_find_box`/`_find_all_boxes`) that reads only box headers
  for anything it doesn't need content from — `mdat` (the audio payload)
  is seeked past, never read. Only the `tsrp`/`keys`/`data` box bodies are
  ever read, each bounded by `_MAX_METADATA_READ` (10 MiB) so a corrupted
  container can't force an unbounded read.
- Both confirmed lookup paths implemented per `tasks/005-...md`'s
  Findings: `.m4a`'s direct `tsrp` under `moov/trak/udta`, and `.qta`'s
  `mdta`/`com.apple.VoiceMemos.tsrp`-keyed entry under a QuickTime-classic
  (no full-box header) `meta` directly under `trak`, resolved via its
  `keys`/`ilst`/`data` chain — including ignoring the `data` box's
  type-indicator field (observed `0` even for JSON text, per Findings).
- Resolved the flagged open item about track-selection: searches **every**
  `trak` under `moov` for either lookup path rather than assuming the
  first one carries the metadata. Tested directly
  (`test_extract_qta_finds_metadata_on_second_track`).
- All seven `status` classifications implemented: `ok`, `empty`, `absent`,
  `unreadable`, `malformed`, `incomplete`, `unsupported`.
- Revised the Phase 1 draft contract itself (recorded in
  `tasks/005-...md`'s "Draft extraction result contract", not just here):
  broadened `malformed` to cover container-structure parse failures (not
  only transcript-JSON parse failures), narrowed `unsupported` to
  extension-only (dropped the unverifiable "differently laid out
  container" clause — a structurally-valid-but-unfamiliar container now
  correctly falls out as `absent` per that status's own definition), and
  extended `locale` to be populated for `incomplete` too.
- Text-run reconstruction concatenates via each run's own `attributeTable`
  index (not positional order) — matches the schema's own indexing rather
  than assuming index == position, per Phase 4's "don't assume a run is a
  word" instruction.
- Timing invariant checks implemented: `runs` length == `2 ×`
  `attributeTable` length, each `timeRange` a valid ascending pair, and
  the `attributeTable` array itself monotonically non-decreasing — any
  violation classifies `incomplete` rather than crashing or guessing.
- 21 tests in `tests/test_extraction.py` covering every status, Unicode
  fidelity (Latin-accented, CJK, and an emoji outside the BMP), a
  synthetic corrupted/truncated container (bounded failure, no crash), a
  byte-count proof that `mdat` is never read
  (`test_moov_lookup_never_reads_mdat_payload`), and a runtime proof that
  extraction never opens a network socket. 81 tests total in the suite;
  `ruff check`/`ruff format --check` clean.
- Built `tests/mp4_builders.py`, a from-scratch synthetic ISO-BMFF/
  QuickTime container builder — this is what Phase 2's deferred
  "synthetic fixture" item was waiting on; it's now populated (as code
  that builds fixtures at test time, which
  `tests/fixtures/synthetic/README.md` already anticipated as a valid
  form).

**Not done yet — next action:**

- None of this has been exercised against a real `.m4a`/`.qta` file —
  only synthetic containers built to match the confirmed byte-level
  structure from `tasks/005-...md`. `ok`/`empty` are the only statuses
  ever confirmed on a real sample (Phase 1); `absent`, `unreadable`,
  `malformed`, `incomplete`, `unsupported` are implemented and
  synthetically tested but not real-sample-confirmed — consistent with
  the deprioritization already recorded in `tasks/005-...md`'s
  Deviations. Real-sample verification is Phase 9's job
  (end-to-end verification).
- No integration with `discovery.py`'s candidates yet — `extract_transcript`
  takes a bare path; wiring it to a `Candidate` and to `state.json` is
  Phase 5/6's job (archive output needs the result; state needs to record
  extraction outcomes for retry tracking).

## Scope and decisions to validate

- [x] Implement bounded container parsing for every verified `.m4a` and
      `.qta` layout, reading only necessary metadata regions rather than
      audio payloads.
- [x] Preserve native Unicode, text order, and meaningful whitespace.
      _Concatenation uses the runs' own embedded spacing (confirmed in
      Phase 1's Findings — first run has no leading space, every
      subsequent run does) with no separator added; Unicode fidelity
      tested directly. No "readable rendering" with added paragraph
      boundaries exists yet — raw native text is the only form produced,
      so there's nothing yet to version separately._
- [x] Preserve native text runs, their available time ranges, and locale
      in the extraction model without assuming a run is a word. _`timing`
      is a list of `(start, end)` pairs aligned 1:1 with `transcript_text`'s
      runs via each run's own `attributeTable` index — not a positional
      assumption._
- [x] Classify blank text separately from absent, malformed, incomplete,
      inaccessible, and unsupported content. _`empty` is its own status,
      tested distinct from all six others._
- [x] Prove through tests that no network call, speech-recognition
      fallback, or Voice Memos database access can occur.
      `test_extraction_never_opens_a_socket` and
      `test_extraction_module_has_no_sqlite_import`.

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 4:

- [x] Each supported layout produces the native transcript or a precise
      non-success classification. _True for every layout confirmed in
      Phase 1 (mono/stereo `.m4a`, spatial `.qta`, either track order),
      verified synthetically; real-sample confirmation is Phase 9's job._
- [x] A blank transcript cannot become a successful archive candidate.
      _`empty` is never `ok`; tested. "Cannot become a successful archive
      candidate" in the full sense (no file written) is enforced by
      Phase 5, which doesn't exist yet — this is the classification-level
      guarantee Phase 4 owns._
- [x] Golden tests establish text fidelity, Unicode behavior,
      timing/locale preservation, and bounded failure on corrupted
      containers. _All four covered in `tests/test_extraction.py`; "golden"
      here means synthetic-but-structurally-faithful, per this file's
      accepted real-sample gap above._

## Session log

_Append one entry per work session: date, what was built/decided, outcome._

- 2026-09-08: Implemented `extraction.py` (bounded atom walker, both
  lookup paths, all seven statuses) and `tests/mp4_builders.py` (synthetic
  container builder). Wrote 21 tests in `tests/test_extraction.py`.
  Revised the Phase 1 draft contract in `tasks/005-...md` (broadened
  `malformed`, narrowed `unsupported`, extended `locale` to `incomplete`).
  Outcome: 81/81 tests pass; `ruff check`/`ruff format --check` clean.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 4
here, per `AGENTS.md`'s working method._

- 2026-09-08: Revised three parts of Phase 1's draft extraction contract
  during implementation rather than treating it as frozen — see the
  "Done" list above and `tasks/005-...md`'s own contract section for the
  full reasoning. This is a refinement of an explicitly-draft artifact
  ("Revise this draft rather than starting a second one as more evidence
  arrives" — tasks/005-...md), not a deviation from the roadmap's actual
  goal or exit criteria for Phase 4.
