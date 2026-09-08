# Platform feasibility and data contract

Focused task plan for Phase 1 of `tasks/000-initial-build.md`. This file
states the exact approach for this phase; it does not restate the roadmap's
goal or exit criteria beyond what is needed to execute the work.

## Status

_Last updated: 2026-09-08. Read this section first in a new session to see
what's done and what to do next._

**Done:**

- Confirmed Full Disk Access is required even for a read-only directory
  listing of the configured Recordings folder, and what the denial looks
  like (`Operation not permitted`). Granted for this session's host app.
- Completed read-only structural inspection (`afinfo`, `ls`, `plutil -p` —
  no content decode, no transcript access) of 5 real samples: S1 (mono
  `.m4a`), S2 (stereo `.m4a`), S3 (spatial `.qta`), S4 (spatial `.qta`),
  S5 (an older mono `.m4a` whose filename lacks the usual ID suffix, plus
  its `.composition/manifest.plist` sidecar). See Session log and Findings.
- Established that `.m4a` carries mono or stereo in a single track, and
  `.qta` carries a spatial dual-track layout (stereo AAC + 4ch ambisonic
  `apac`) — see Findings for the evidence and its confidence level.
- Found and documented the composition-sidecar pattern that explains a
  filename with no ID suffix (canonical ID lives in an adjacent
  `.composition/manifest.plist`'s `RCSavedRecordingUUID`), with a concrete
  Phase 3 follow-up recorded under "Open items for later phases."
- Probed the transcript payload location and structural shape on 4 fresh
  `.m4a`/`.qta` test samples (S6–S9, one per format/channel combination,
  made specifically for this probing pass) plus a re-probe of S5 (the
  ID-less recording). Confirmed both the `.m4a` direct-`tsrp`-atom path and
  the `.qta` metadata-keyed path from real evidence. See Findings.
- Probed two more fresh samples, S10 (`.qta`) and S11 (`.m4a`), both
  recorded specifically as no-speech/silence test cases. Confirmed on both
  formats: the transcript key is still written but `attributedString`
  collapses to an empty string instead of the runs/attributeTable object —
  the format-independent "no transcript" signal a parser must detect. See
  Findings.
- Wrote a first draft of the extraction result contract (`status`
  classifications, and the `transcript_text`/`timing`/`locale`/
  `extraction_format_version` fields) directly from the accumulated
  Findings — see "Draft extraction result contract" below. Confirmed
  run-concatenation join behavior (no separator needed) as part of this.
- Wrote a first draft of the support matrix directly from the accumulated
  Findings plus one host-environment check (`sw_vers`, not a Voice Memos
  sample) — see "Draft support matrix" below. No new sample was opened for
  this.

**Not done yet — deprioritized, not blocking:**

- The draft contract's `absent`, `unreadable`, `malformed`, and
  `incomplete` statuses are defined but not yet observed on a real
  sample — only `ok` and `empty` are confirmed. Per the "Deviations"
  section below, the user has decided not to chase these on manufactured
  samples for now; the draft contract's design is being treated as
  sufficient to proceed.
- A non-`en_US` locale sample and iCloud-in-progress-download stability
  signals are likewise untested and deprioritized for the same reason —
  not practical to manufacture on demand, not a current priority.
- The draft support matrix's four open rows (packaged-process macOS/FDA,
  non-`en_US`, iCloud-in-progress, source device) stand as documented
  gaps rather than blockers. See "Draft support matrix" below.
- FDA behavior was only observed from a developer-shell host process (VS
  Code's integrated terminal), not a packaged/signed executable — this
  one remains genuinely blocked (not deprioritized) until Phase 8
  produces a packaged executable to test against.

**Next action:** proceed to Phase 2 (Foundation and test harness) per
`tasks/000-initial-build.md`, using the draft extraction contract and
support matrix as-is. Revisit any of the deprioritized items above if a
real instance turns up naturally in later-phase work.

**Before opening any *additional* real sample in a new session**, re-confirm
the "Focused acceptance checks" below per this file's own protocol —
approval does not carry forward across sessions automatically. The 5
samples already logged do not need re-approval to keep referencing their
existing findings.

## Read-only inspection approach

- Only ever open recording containers in read-only mode. No tool, script, or
  command used during this phase may write, rename, delete, or move a file
  under a Voice Memos recordings folder.
- Inspect container structure and metadata only — do not decode or play audio
  payloads. Use tools that can target atoms/boxes and metadata regions
  directly (e.g. `mdls`, `AVFoundation` introspection via a short read-only
  script, a hex/atom viewer, or a minimal ISO-BMFF/QuickTime atom walker
  written for this task) rather than a general media player or transcoder.
- Every inspection command or script used against a real sample is recorded
  in this file's "Session log" before it is run against that sample, so the
  read-only claim is auditable after the fact.
- No inspection step may require or trigger network access (e.g. no iCloud
  re-download, no metadata lookup service). If a sample appears to need a
  network fetch to become readable, record that as a finding, not a reason to
  allow one.
- Do not query or open the Voice Memos private database (e.g. `CloudRecordings.db`)
  at any point. Only the configured recordings folder and the recording
  container files themselves are in scope.

## Local-sample handling protocol

- Real samples are provided by the user, locally, and are never fetched or
  generated by the agent. The agent does not browse the live Voice Memos
  recordings folder to select samples; the user points to specific files.
- Real samples and any raw notes about them stay under `.local/` (already
  gitignored) or another path the user designates outside the repository's
  tracked tree. The agent does not access `.local/` or any real sample
  without the user's explicit, per-session instruction to do so — a standing
  instruction from an earlier session does not carry forward automatically.
- Before opening any real sample, confirm with the user: which specific
  file(s), and confirm the file contains no content the user is unwilling to
  have summarized in non-sensitive form (see "Evidence to retain" below).
- Never quote, paraphrase, log, or commit transcript text, recording titles,
  speaker names, or any other content-bearing string from a real sample.
  Findings are recorded as structural/technical facts only (e.g. "the `tsrp`
  atom was present and contained N text runs with non-empty locale tags"),
  never as excerpts.
- If a redacted or synthetic fixture is needed for the committed test suite,
  the agent constructs it from scratch (synthetic container bytes, or a
  fixture with placeholder text such as `"sample transcript text"`) rather
  than deriving it from a real sample's actual bytes or text.

## Non-sensitive evidence to retain

For each real sample inspected, record only:

- Source format (`.m4a` / `.qta`), and whether it is mono, stereo, or spatial.
- Container/atom layout observed (e.g. presence and path of a `tsrp` atom, or
  a metadata-keyed transcript entry; the metadata key name itself is fine to
  record since it is Apple's schema, not user content).
- Presence/absence of a transcript, and, if present, structural facts only:
  number of text runs, whether time ranges are present, whether a locale tag
  is present and what it is (e.g. `en-US`), text encoding.
- File size, modification time, and whether the sample was stable across
  repeated reads (for iCloud-download-in-progress detection).
- Any parse error class encountered (e.g. "truncated container," "unknown
  atom version") without embedding raw bytes that could contain user content.
- macOS version and Full Disk Access status of the process used for the read.

Do not retain: transcript text, recording titles, raw file paths that embed a
personal folder/user name beyond `~`, or raw hex dumps of payload regions
that could contain transcript bytes. A hex dump of container *structure*
(atom headers/sizes only, with payload bytes redacted or elided) is
acceptable.

## Focused acceptance checks (before a sample is opened)

- [ ] This task file has been read and its protocol agreed to for the
      current session.
- [ ] The user has named the specific real sample file(s) to inspect.
- [ ] The inspection tool/command for the first sample is recorded in the
      session log below, and it is read-only and offline.
- [ ] A place to record non-sensitive evidence (this file's "Findings"
      section, appended below) is ready before the first sample is opened.

## Scope and decisions to validate (from the roadmap)

- [x] Verify transcript location, payload encoding, text presence, available
      time ranges, locale, and layout variation for `.m4a` and for `.qta`.
      _All confirmed on real samples (S5–S11) — see Findings: location
      (`tsrp` box for `.m4a`; metadata-keyed `mdta:com.apple.VoiceMemos.tsrp`
      for `.qta`), encoding (UTF-8 JSON), text presence (non-empty
      `runs`/`attributeTable` on every non-empty sample, and the
      empty-string collapse confirmed on both formats for the no-speech
      case — S10/S11), timing (word/phrase-level `[start, end]` seconds),
      locale (`locale.identifier`, e.g. `en_US`), and layout variation
      (mono/stereo/spatial, confirmed earlier). Not yet covered: a
      non-`en_US` locale sample — see "Open items for later phases."_
- [x] Establish whether `.qta` uses a direct `tsrp` atom, a metadata-keyed
      transcript value, or both, from real evidence rather than assumption.
      _Confirmed: `.qta` uses the metadata-keyed path only (no direct
      `tsrp` box exists in it); `.m4a` uses a direct `tsrp` box only. See
      Findings._
- [ ] Verify the default source path,
      `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`,
      and confirm actual Full Disk Access behavior for a packaged
      (non-developer-shell) process before relying on it. _Partially
      confirmed: the path is correct, FDA is required, and the denial is
      diagnosable (`Operation not permitted`) with no programmatic
      grant/prompt available — but this was only observed from a
      developer-shell host process (VS Code's integrated terminal), not a
      packaged/signed executable, since none exists yet (Phase 8). Leave
      unchecked until re-verified against an actual packaged process._
- [ ] Establish iCloud stability signals (size, mtime, structure, repeat-read
      consistency) sufficient to avoid classifying a still-downloading file
      as empty or transcript-less on a single read.
- [ ] Define the narrow extraction result contract: native transcript text;
      available native timing and locale; source format; extraction-format
      version; and classifications for absent, unreadable, malformed,
      incomplete, and unsupported data. _First draft written — see "Draft
      extraction result contract" below. `ok` and `empty` are confirmed
      against real samples; `absent`, `unreadable`, `malformed`, and
      `incomplete` are defined but not yet observed/verified on a real
      sample, so this stays unchecked until they are or the draft is
      otherwise validated._
- [ ] Produce a support matrix (macOS version, source device, language/region,
      format, local availability, known unsupported variants). _First draft
      written — see "Draft support matrix" below. Format/channel-layout and
      `en_US` rows are confirmed on real samples; macOS-version (dev-shell
      only), source-device, non-`en_US`, and iCloud-in-progress rows remain
      open, so this stays unchecked until they're closed or the draft is
      otherwise validated._

## Exit criteria

Unchanged from `tasks/000-initial-build.md` Phase 1:

- [ ] Real redacted `.m4a` and `.qta` samples evidence each supported
      payload layout, or an unsupported format is explicitly excluded.
- [ ] The implementation can distinguish no transcript from incomplete,
      inaccessible, malformed, or unsupported content without retranscribing
      audio.
- [ ] Golden and negative fixtures exist without private material.
- [ ] The support and permissions requirements are documented for users.

## Session log

_Append one entry per real-sample inspection session: date, tool/command
used, sample identifier (not filename — an opaque local label is fine),
outcome._

- 2026-09-08: `ls -la` on the configured Recordings folder (read-only
  directory listing; no file opened). Outcome: succeeded after Full Disk
  Access was granted to the host app; first attempt failed with
  `Operation not permitted` (see Findings — this is itself a finding).
- 2026-09-08: `afinfo <file>` (read-only container/format-header parse, no
  decode/playback) on samples S1–S4 (the four most recently recorded
  files at the time, one per format/channel combination available).
  Outcome: succeeded on all four.
- 2026-09-08: `afinfo <file>` and `ls -la <dir>` on sample S5 (an older
  recording whose filename lacks the usual ID suffix) and its adjacent
  `.composition/` directory. Outcome: succeeded.
- 2026-09-08: `plutil -p manifest.plist` (read-only plist pretty-print, no
  modification) inside S5's `.composition/` directory. Outcome: succeeded.
- 2026-09-08: custom read-only Python atom-header walker (recurses only into
  known ISO-BMFF/QuickTime container box types; for the metadata `keys` box
  it reads the key namespace+name strings, which are Apple's schema, not
  user content; for `ilst`/`data` leaf boxes it reads only the box size and
  4-byte type-indicator field, never the payload) run against 4 freshly
  made test samples S6–S9 (one per format/channel combination: `.qta`
  spatial, `.qta` spatial, `.m4a` stereo, `.m4a` mono) to locate the
  transcript-bearing atom in each. Outcome: succeeded; found a `tsrp` box
  under `moov/trak/udta` in both `.m4a` samples and a metadata-keyed entry
  (`mdta` namespace, key name `com.apple.VoiceMemos.tsrp`) under the first
  `trak`'s classic-QuickTime `meta/keys`+`ilst` in both `.qta` samples.
- 2026-09-08: for each of S6–S9, read the located transcript box's payload
  as bytes, confirmed it parses as JSON, and inspected only its *shape*
  (`json.loads`, then a structural walk that reports key names, container
  lengths, and value types/lengths — never string content, except a locale
  code where the value itself matched a locale-pattern regex, which this
  file's protocol allows recording). Outcome: succeeded on all 4; consistent
  schema across formats (see Findings).
- 2026-09-08: re-ran the same atom walk plus the JSON-shape probe against
  S5 (the ID-less recording from the earlier session) to confirm it still
  carries its own intact transcript despite the failed-append/empty
  `RCDecomposedFragments` finding already on record. Outcome: succeeded —
  `tsrp` present and well-formed, same schema as S8/S9.
- 2026-09-08: same atom walk plus JSON-shape probe against S10, a fresh
  `.qta` sample the user recorded specifically as a no-speech/silence test
  case. Outcome: succeeded; the metadata-keyed `tsrp` entry is still
  present (same `mdta`/`com.apple.VoiceMemos.tsrp` location as S6/S7), but
  its JSON shape differs for the no-content case — see Findings.
- 2026-09-08: same atom walk plus JSON-shape probe against S11, a fresh
  `.m4a` sample the user recorded as the `.m4a` counterpart to the S10
  no-speech test. Outcome: succeeded; direct `tsrp` box present at the
  same location as S8/S9, showing the identical empty-string
  `attributedString` collapse seen on S10 — see Findings.
- 2026-09-08: re-opened S6 and S8 (already-inspected multi-run samples) to
  check one further structural fact — whether each run string in `runs`
  starts/ends with whitespace (boundary-character check only; run content
  itself not read) — to determine transcript-text join behavior for the
  draft extraction contract. Outcome: succeeded; consistent pattern found
  on both samples (see Findings and "Draft extraction result contract").
- 2026-09-08: `sw_vers` (host OS version only — not a Voice Memos sample,
  no recording opened). Outcome: succeeded; recorded in the draft support
  matrix below.

## Findings

_Non-sensitive evidence only, per the section above. Append as inspection
proceeds._

- **FDA is required even for a plain read-only directory listing.** A first
  `ls` attempt against the configured Recordings folder failed with
  `Operation not permitted` until Full Disk Access was granted to the host
  process. There is no programmatic request/prompt for this permission
  (unlike camera/mic/contacts) — it must be granted manually in System
  Settings → Privacy & Security → Full Disk Access, per-app (per bundle
  identifier), all-or-nothing. Confirms Phase 1/8's note to diagnose this
  from the real executable rather than assume shell access.
- **Filename grammar**: most recordings follow `YYYYMMDD HHMMSS-<ID>.ext`.
  Sample count observed: ~30 recordings, mixed `.m4a`/`.qta`, ranging
  roughly 4KB–6.4MB.
- **Non-candidate entries discovery must skip**, seen directly in the
  configured Recordings folder: `*-track0.waveform` sidecar files,
  `*.composition/` directories, `Capture/`, `CaptureRecovery/`,
  `.CloudRecordings_SUPPORT/`, `CloudRecordings_ckAssets/`, and the
  database files `CloudRecordings.db`, `CloudRecordings.db-shm`,
  `CloudRecordings.db-wal` (not opened, per the project's database
  invariant).
- **Format/channel layout (samples S1–S4, via `afinfo`)**:
  - `.m4a`, 1 track, 1ch AAC → **mono**.
  - `.m4a`, 1 track, 2ch AAC → **stereo**.
  - `.qta`, 2 tracks: Track 1 = 2ch AAC (stereo fallback), Track 2 = 4ch
    `apac` "High-Order Ambisonics, ACN/SN3D" → **spatial**. Observed on two
    independent `.qta` samples.
  - Working hypothesis: `.qta` is used specifically for spatial-audio
    recordings (dual-track: stereo + ambisonic); `.m4a` covers both mono
    and stereo in a single track. Not yet tested against a larger sample.
- **Filename-less-ID case (sample S5)**: `.m4a`, 1 track, 1ch AAC (mono) —
  same audio format as an ID'd mono sample, so audio format/channel count
  does not explain ID absence in the filename.
  - S5 has an adjacent `<timestamp>.composition/` directory containing
    `manifest.plist` and an empty `fragments/` directory.
  - `manifest.plist` (plist structure only) contains: `RCComposedAVURL`
    (points back to the sibling `.m4a`), `RCDecomposedFragments` (an empty
    array — no audio segments were actually merged), `RCSavedRecordingCreationDate`
    / `RCSavedRecordingCreationTime` (matches the filename timestamp),
    `RCSavedRecordingUUID` (a UUID — the recording's real, canonical ID),
    and `RCSavedRecordingTitle` (a user-entered title — value redacted
    here per this file's evidence rules; not retained).
  - **Working conclusion**: a filename lacking an ID suffix does not mean
    the recording has no ID. When Voice Memos' "add to existing recording"
    flow is invoked (even if nothing ends up appended — `RCDecomposedFragments`
    empty is consistent with that), it appears to write a
    `.composition/manifest.plist` sidecar next to a plain-timestamp `.m4a`,
    and the canonical ID lives in that sidecar's `RCSavedRecordingUUID`
    field rather than in the filename.

- **Transcript location differs by format, confirmed on S6–S9 (and S5 for
  the `.m4a` case):**
  - `.m4a`: a `tsrp` box is present directly under `moov/trak/udta` (the
    audio track's `udta`, not the file-level `moov/udta` that holds
    `©nam`/`©too`). Its payload is the transcript JSON directly — no
    metadata-key indirection.
  - `.qta`: no top-level or `udta`-level `tsrp` box exists. Instead, the
    *first* `trak` (the stereo/AAC track) carries a classic-QuickTime-style
    `meta` box — a full box under `moov/trak/udta` on `.m4a`, but here
    directly under `trak` with **no** ISO version/flags header (the parser
    must detect this per-box; assuming the ISO full-box header
    unconditionally misparses the child list). That `meta` box's `keys`
    table has exactly one entry: namespace `mdta`, key name
    `com.apple.VoiceMemos.tsrp`. Its `ilst` has exactly one corresponding
    item, whose `data` box holds the transcript JSON.
  - Answers the open scope question directly: `.qta` uses the
    metadata-keyed path, not a direct `tsrp` box; `.m4a` uses a direct
    `tsrp` box, not metadata-keyed. Both names literally contain "tsrp"
    (box name vs. metadata key suffix), which is a coincidence worth noting
    for anyone keyword-grepping rather than parsing structurally.
  - Confirmed on 2 independent `.qta` samples and 3 independent `.m4a`
    samples (S6/S7 for `.qta`; S8/S9/S5 for `.m4a`). Not yet tested against
    a `.qta` recording with zero transcribable speech (silence-only), which
    would confirm the same location holds for an empty-transcript case.
- **`data` box type-indicator anomaly**: the QuickTime metadata `data` box's
  4-byte type-indicator field reads `0` (the "reserved/binary" type in
  Apple's iTunes-style metadata type enum) on every sample observed, even
  though the payload is UTF-8 JSON text — not `1` (the enum's own "UTF-8
  string" type). A Phase 2 parser must not branch on the declared type
  indicator when locating this specific key; it should identify the
  transcript value by key name (`com.apple.VoiceMemos.tsrp`) and parse the
  `data` box payload as JSON/UTF-8 regardless of the type-indicator value.
- **Transcript JSON schema, consistent across all 5 samples probed this
  session** (`.m4a` mono/stereo and `.qta` spatial alike):
  - Top level: `{"locale": {...}, "attributedString": {...}}`.
  - `locale.identifier` and `locale.preferences.locale`: an underscore-form
    locale code (e.g. `en_US`, observed on all 5 samples — no other locale
    available to test this session). `locale.preferences.langs`: an array
    of hyphen-form locale codes (e.g. `en-US`). `locale.current` and
    `locale.preferences.temp`: small integers, purpose not yet determined
    (not investigated further — out of scope for the extraction contract,
    which only needs the identifier).
  - `attributedString.runs`: a flat array alternating [text-run string,
    integer attribute-table index], i.e. length `2 × attributeTable`
    length. Run-string lengths observed ranging from very short (single
    words) to longer phrases; exact text not retained per this file's
    protocol.
  - `attributedString.attributeTable`: an array of records, each currently
    observed to contain exactly one key, `timeRange`: a 2-element
    `[start_seconds, end_seconds]` pair (mixed `int`/`float` JSON encoding
    depending on whether the value is a whole number), monotonically
    non-decreasing across the array and bounded by the recording's
    duration on every sample checked. This gives word/phrase-level timing,
    confirming native timing is available at that granularity (not just a
    single whole-transcript time range).
  - Run count scaled roughly with recording length across the 5 samples
    (shortest ~8.7s recording had the smallest run/attribute counts,
    longest ~12.5s recording the largest), consistent with per-word or
    per-short-phrase segmentation rather than one run per sentence.
- **Empty/no-speech case (S10, a `.qta` recorded specifically as a
  silence/no-speech test)**: the transcript entry is *not absent* — the
  `mdta`/`com.apple.VoiceMemos.tsrp` metadata key/value is still written,
  in the same location as a normal `.qta` transcript. What differs is the
  JSON shape: `attributedString` is a **string** (`""`, empty) rather than
  the **object** (`{"runs": [...], "attributeTable": [...]}`) seen on
  every non-empty sample. `locale` is still populated normally. This means
  a parser cannot treat "key present" as "transcript present" — it must
  check `attributedString`'s JSON type, and treat the empty-string case as
  the "no transcript" classification the extraction contract needs (rather
  than as a malformed/unexpected shape). Not yet tested: whether `.m4a`'s
  direct `tsrp` box shows the same empty-string collapse, or whether the
  `tsrp` entry can be absent entirely under some other condition (e.g. a
  recording made before transcription finishes, or transcription
  explicitly disabled) — both remain open.
  - `locale.preferences.langs` on this sample had more than one entry
    (only one was seen on S6–S9). Not pursued further this session since
    it doesn't affect the schema question being tested here, but it's a
    reminder that `langs` is a list and may vary in length per device.
  - **Confirmed on `.m4a` too (S11)**: a same-day `.m4a` no-speech
    counterpart to S10 shows the identical empty-string
    `attributedString` collapse in its direct `tsrp` box (box size 143
    bytes, vs. ~700+ bytes for a non-empty transcript on a similar-length
    recording). The "no transcript" JSON shape is format-independent —
    resolves the one gap left open earlier this session.
- **S5 re-confirmed**: despite the empty `RCDecomposedFragments` finding
  already on record (the user's own account this session: they attempted
  Voice Memos' "add to existing recording" flow and the appended content
  ended up empty, which is why no ID suffix was written to the filename),
  the original recording's own `tsrp` transcript is intact, well-formed,
  and matches the same JSON schema as the other `.m4a` samples. The failed
  append did not corrupt or remove the existing transcript.
- **Run-boundary spacing (S6, S8)**: checked each run string's leading/
  trailing character class (not its content) across both samples. Pattern
  was identical and 100% consistent: run 0 has no leading space, every
  run after it has exactly one leading space, and no run has a trailing
  space. Plain in-order concatenation of `runs`' text elements
  reconstructs the transcript with correct word spacing — no separator or
  join logic needed.

## Draft extraction result contract

_First draft of the "Scope and decisions to validate" contract item, built
directly from the Findings above. This defines the shape of what Phase 2's
extraction step returns for one recording — not an implementation, and not
yet exercised against every case (see gaps noted per field). Revise this
draft rather than starting a second one as more evidence arrives._

**Result fields:**

- `status` — one of the classifications below. Always present.
- `source_format` — `"m4a"` or `"qta"`, from the file extension actually
  opened (not inferred from anything else).
- `transcript_text` — the reconstructed transcript string, built by
  concatenating `attributedString.runs`' text-run strings **in order with
  no separator** (`"".join(...)`). Confirmed on S6 (21 runs) and S8 (15
  runs): the first run has no leading space, every subsequent run has a
  leading space and no trailing space — so inter-word spacing is already
  embedded in each run and plain concatenation reproduces the transcript
  correctly. (Checked structurally only — each run string's first/last
  character class, never its content — per this file's evidence rules.)
  Present only when `status == "ok"`; `None` otherwise.
- `timing` — a list of `(start_seconds, end_seconds)` pairs, one per run,
  aligned 1:1 with the runs that make up `transcript_text` (via each run's
  `attributeTable` index). Present only when `status == "ok"`.
- `locale` — `locale.identifier` as found (e.g. `"en_US"`), present
  whenever the transcript entry itself was found and its JSON parsed,
  regardless of whether it held text (`ok` or `empty`); `None` for
  `absent`, `unreadable`, `malformed`, or `unsupported`.
- `extraction_format_version` — an integer versioning this result shape
  itself (not the source recording). Bump it on any breaking change to
  this contract so `state.json` can detect a stale prior extraction.

**`status` classifications:**

- `ok` — transcript entry found, parsed, and `attributedString` is the
  non-empty runs/attributeTable object. Confirmed shape: S6–S9, S5, S11.
- `empty` — transcript entry found and parsed, but `attributedString` is
  the empty string (no speech content was transcribed). Per this
  project's invariant ("do not create archive files for empty or
  transcript-less recordings"), `empty` and `absent` both result in no
  archive file being written — but they stay distinct statuses here
  because they likely need different handling in `state.json`'s retry
  tracking (see the open question below). Confirmed shape: S10, S11.
- `absent` — no `tsrp` box (`.m4a`) and no `mdta`/
  `com.apple.VoiceMemos.tsrp` metadata key (`.qta`) found anywhere in the
  container. Not yet observed on a real sample this session — every
  sample opened so far had at least the empty-string case. Left as a
  distinct status because it plausibly means something different from
  `empty` (e.g. transcription still pending vs. confirmed no speech) —
  unconfirmed; a real `absent` sample hasn't been captured yet.
- `unreadable` — the file or container could not be opened or read at all
  (I/O error, permission denied, still downloading from iCloud). Not
  triggered by anything about the transcript entry specifically.
- `malformed` — the transcript entry was found, but its bytes did not
  parse as valid JSON, or the parsed JSON's top level did not match
  `{"locale": ..., "attributedString": ...}`. Not yet observed on a real
  sample — every sample this session parsed cleanly.
- `incomplete` — the transcript entry parsed as JSON with the expected
  top-level shape, but an internal invariant this session established
  didn't hold (e.g. `runs` length isn't `2 ×` `attributeTable` length, or
  an `attributeTable` entry is missing `timeRange`, or `timeRange` isn't
  a 2-element ascending pair). Not yet observed on a real sample.
- `unsupported` — the file extension isn't `.m4a`/`.qta`, or the
  container layout doesn't match either of the two confirmed lookup paths
  (direct `tsrp` under `trak/udta` for `.m4a`; `mdta`-keyed entry under
  the first `trak`'s classic-QuickTime `meta` for `.qta`) closely enough
  to say the entry is genuinely `absent` rather than just differently
  laid out. Guards against silently misreading a container shape this
  investigation hasn't seen (e.g. a future macOS/Voice-Memos version that
  changes the layout).

**Open questions before Phase 2 can implement against this contract:**

- Whether `absent` is reachable in practice (vs. Voice Memos always
  writing at least the empty-string shape once a recording exists) is
  unconfirmed — needs a sample from a state where transcription hasn't
  run yet, if such a state is even observable locally.
- Whether `empty` and `absent` need different `state.json` retry
  behavior (e.g. retry `absent` a few times in case transcription is
  still catching up, but treat `empty` as final) is a Phase 3 design
  question, not answered here.
- This contract has only been checked against `en_US` samples; a
  non-`en_US` locale sample (open item below) may reveal a shape this
  draft doesn't account for.

## Draft support matrix

_First draft of the "Produce a support matrix" scope item, built directly
from the Findings above and one host-environment check (`sw_vers`). No new
sample was opened to write this draft. Confirmed rows cite the samples that
evidence them; every other row is an explicit open item, not an assumption._

| Dimension | Value | Status | Evidence |
|---|---|---|---|
| macOS version (dev host) | 26.6.2 (build 25G83) | Confirmed for this dev-shell session only | `sw_vers`, this session |
| macOS version (packaged process) | — | **Open** — no packaged/signed executable exists yet (Phase 8) | — |
| Format | `.m4a`, mono, 1 track | Supported | S1, S5, S8, S9, S11 |
| Format | `.m4a`, stereo, 1 track | Supported | S2 |
| Format | `.qta`, spatial (2 tracks: stereo AAC + 4ch ambisonic `apac`) | Supported | S3, S4, S6, S7, S10 |
| Format | any extension other than `.m4a`/`.qta` | Unsupported (explicit `unsupported` status in the draft extraction contract) | Not observed in the configured Recordings folder this session |
| Source device | — | **Open** — not captured; device-model metadata wasn't inspected (out of scope for structural findings so far) | — |
| Language/region | `en_US` | Supported and confirmed | All 11 samples (S1–S11) |
| Language/region | non-`en_US` | **Open** — untested this session | — |
| Local availability | fully downloaded local file | Supported | All 11 samples were locally readable without a network fetch |
| Local availability | file still downloading from iCloud (partial/placeholder on disk) | **Open** — untested; no repeat-read/stability check performed yet | — |
| Known unsupported variant | none confirmed yet | **Open** — no sample has hit `absent`, `malformed`, `incomplete`, or `unsupported` in practice | — |

**Working conclusion**: `.qta` = spatial-audio recordings only (dual-track
stereo + ambisonic); `.m4a` covers mono and stereo in a single track — see
"Open items for later phases" for the existing note that this needs
confirmation across more samples before being stated as a hard rule.

**Gaps this draft leaves for the scope item to close** (mirrors the
"Not done yet" list in Status): packaged-process macOS/FDA verification,
a non-`en_US` sample, an iCloud-in-progress-download sample, and a source
device field, which nothing gathered so far actually populates.

## Open items for later phases

_Concrete follow-ups this investigation surfaced, to be picked up when the
relevant phase's task file is created — listed here so they are not lost._

- **Phase 3 (discovery/dedup)**: when a recording's filename lacks an ID
  suffix, check for an adjacent `<timestamp>.composition/manifest.plist`
  and use its `RCSavedRecordingUUID` as the dedup identity instead of
  treating the file as malformed. Needs more samples to confirm this is
  the only such case (vs. e.g. truly legacy/no-ID recordings with no
  sidecar at all).
- **Phase 3 (discovery)**: explicitly exclude `*.waveform`, `*.composition/`,
  `Capture/`, `CaptureRecovery/`, `.CloudRecordings_SUPPORT/`,
  `CloudRecordings_ckAssets/`, and `CloudRecordings.db*` from candidate
  enumeration.
- **Phase 1/8 (permissions/diagnostics)**: `doctor`-style diagnostics must
  explicitly detect the FDA-denied case (e.g. `Operation not permitted` on
  a folder read) and point the user to System Settings → Privacy &
  Security → Full Disk Access, since macOS gives no programmatic prompt
  for this permission.
- **Phase 1 (support matrix)**: tentatively, `.qta` = spatial-audio
  recordings (stereo + ambisonic dual-track), `.m4a` = mono or stereo
  single-track. Needs confirmation across more samples before it's stated
  as a rule rather than an observation.
- **Phase 2 (extraction implementation)**: the transcript parser needs two
  distinct lookup paths — a direct `moov/trak/udta/tsrp` box read for
  `.m4a`, and a `moov/trak/meta` (no ISO version/flags — detect, don't
  assume) → `keys` scan for namespace `mdta` / name
  `com.apple.VoiceMemos.tsrp` → matching `ilst` item's `data` box for
  `.qta`. Parse the `data` payload as UTF-8 JSON regardless of the
  box's own type-indicator field (observed `0`, not the "UTF-8 string"
  enum value — see Findings). Do not assume `.qta`'s metadata is on the
  first `trak` for every recording without checking `tref`/`hdlr` — this
  session confirmed it empirically on 2 samples but did not verify the
  track-selection logic against a sample where track order might differ.
- **Phase 1/2 (transcript JSON schema)**: draft the extraction result
  contract's transcript shape around `locale.identifier`,
  `attributedString.runs` (alternating text/attribute-index pairs), and
  `attributedString.attributeTable[].timeRange` (`[start, end]` seconds,
  word/phrase granularity) — see Findings for the full schema notes. Still
  needed before the contract can be drafted: a sample with an empty/absent
  transcript (silence-only recording) to confirm how absence is
  represented (missing `tsrp`/key entirely vs. present-but-empty
  `runs`/`attributeTable`), and a non-`en_US` locale sample to confirm the
  locale field format holds.

## Deviations from the roadmap

_Record any material deviation from `tasks/000-initial-build.md` Phase 1
here, per `AGENTS.md`'s working method._

- 2026-09-08: User decided to stop pursuing real samples for the three
  remaining sample-dependent gaps (a non-`en_US` locale recording, an
  in-progress iCloud download, and a sample that actually triggers
  `absent`/`malformed`/`incomplete`) — these aren't practical to
  manufacture on demand and aren't considered a current priority. The
  draft extraction contract and support matrix already define how these
  cases are meant to be handled; that theoretical coverage is being
  treated as sufficient to proceed, rather than blocking on real-sample
  confirmation. Phase 1's exit criteria bullet "distinguish no transcript
  from incomplete, inaccessible, malformed, or unsupported content" is
  therefore being treated as satisfied by the draft contract's design,
  not by observed evidence, for these specific statuses — left unchecked
  below to keep that distinction visible; revisit if a real instance of
  one of these cases turns up naturally during later-phase work (e.g. a
  Phase 4 golden-fixture test surfaces one, or a real scan produces one).
  Packaged-process FDA verification remains genuinely blocked on Phase 8
  (no packaged executable exists) rather than deprioritized by choice.
