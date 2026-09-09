# Initial build plan

## Purpose

Build a local, read-only macOS utility that preserves the native Apple Voice Memos transcript already present in a recording as a durable, app-independent Markdown archive. The archive is the durable source of truth; operational JSON is rebuildable bookkeeping only.

This plan translates the settled product intent into an ordered engineering roadmap. It does not replace or restate that intent.

## How this plan is used

This document is the master roadmap for the initial release. It records phases, dependencies, important decisions to validate, and their exit criteria. Its sections contain the full known scope for the initial build, but they are not yet active implementation tasks.

Immediately before a phase starts, create a focused, numbered task file based on its section—for example, `005-platform-feasibility-and-data-contract.md`. That task file must state the exact approach, tests, acceptance checks, discoveries, and any material deviation from this plan. Mark a phase complete here only after its task file’s verification is complete.

When an issue changes product intent, update the brief first. When it changes sequencing, scope, or a cross-cutting technical decision, update this plan. When it changes only the exact work of an active phase, update that phase’s task file.

## Build order

0. [x] Repository baseline and privacy preflight
1. [ ] Platform feasibility and data contract
2. [x] Foundation and test harness
3. [ ] File discovery and source metadata
4. [x] Native transcript extraction and fidelity
5. [ ] Archive output, deduplication, and conflicts
6. [ ] Operational state, retries, and recovery
7. [ ] Setup, automation, and diagnostics
8. [ ] Packaging, permissions, and privacy
9. [ ] End-to-end verification and release readiness

No implementation phase begins until its stated dependencies and exit criteria are met. A failure to validate an Apple format must create a visible unsupported case or a revised plan; it must not trigger a fallback to third-party transcription.

## Phase 0: Repository baseline and privacy preflight

### Goal

Establish a clean, committed public planning baseline and prove that local-only project context cannot enter the repository before any implementation or local fixture investigation begins.

### Dependencies

None.

### Scope and decisions to validate

- Commit the public repository baseline: `.gitignore`, `AGENTS.md`, `CLAUDE.md`, and this initial build plan. Do not add local context, local research, personal recordings, transcript text, identifiers, or raw observations.
- Verify that `.local/` is ignored and that no tracked file links to or names a private local-context file. Keep public planning material self-contained.
- Confirm that the repository has no source code, dependencies, services, or configuration that can make a network request, access the Voice Memos private database, or write under Voice Memos storage.
- Immediately before Phase 1 begins, create `tasks/005-platform-feasibility-and-data-contract.md`. It must define the exact read-only inspection approach, the local-sample handling protocol, the non-sensitive evidence to retain, and focused acceptance checks before a sample is opened.
- Defer public support claims and a public README until Phase 1 has verified the real source formats and limits. Do not let a placeholder promise unverified `.m4a` or `.qta` support.

### Exit criteria

- [x] The public planning baseline is committed, and `git status` contains no accidental private or fixture material.
- [x] Ignore rules and tracked-content checks demonstrate that `.local/` remains local-only and unreferenced by public files.
- [x] The focused Phase 1 task plan exists and preserves the read-only, no-network, no-database boundaries.

## Phase 1: Platform feasibility and data contract

### Goal

Prove the local, native-transcript extraction path on supported recordings and establish a precise source contract before production implementation.

### Dependencies

None.

### Scope and decisions to validate

- Use a small, explicitly redacted local fixture corpus: completed mono, stereo, and spatial `.m4a` and `.qta` recordings with visible Apple transcripts, plus transcript-less, incomplete, zero-byte, renamed, and malformed examples. No personal audio, titles, identifiers, or transcript text may be committed.
- Inspect the recording containers read-only and without loading audio payloads. Verify transcript location, payload encoding, text, available time ranges, locale, and layout variation for each supported source type.
- Recent `.m4a` recordings are known to use an embedded transcript representation. `.qta` is QuickTime Audio and may use a distinct metadata layout; candidate layouts include a direct `tsrp` atom and a metadata-keyed transcript value. Record the verified layout rather than inferring it from the extension; both formats must be established using real, redacted samples before the extractor contract is frozen.
- Verify the default source path, `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`, and the actual macOS privacy behavior for the packaged process. Full Disk Access must be diagnosed in the installed executable, not assumed from a developer shell.
- Establish iCloud stability signals: file size, modification time, readable container structure, and observations across scans. A single transient read must never classify a memo as empty or transcript-less.
- Publish a support matrix for macOS, source-device transcript availability, language/region, source format, local availability, and known unsupported variants. The archiver has no Apple-silicon prerequisite of its own: it archives only transcript data already embedded in the recording. Apple does not publish this binary format as an API, so the contract is version-sensitive.
- Define a narrow extraction result: native transcript text; available native timing and locale; source format; extraction-format version; and classifications for absent, unreadable, malformed, incomplete, and unsupported data.

### Exit criteria

- [ ] Real redacted `.m4a` and `.qta` samples evidence each supported payload layout, or an unsupported format is explicitly excluded.
- [ ] The implementation can distinguish no transcript from incomplete, inaccessible, malformed, or unsupported content without retranscribing audio.
- [ ] Golden and negative fixtures exist without private material.
- [ ] The support and permissions requirements are documented for users.

## Phase 2: Foundation and test harness

### Goal

Establish stable module boundaries, schemas, error vocabulary, safe persistence primitives, and a privacy-safe automated test environment.

### Dependencies

Phase 1 has defined the extraction result contract.

### Scope and decisions to validate

- Separate configuration, operational state, discovery, extraction, archiving, scheduling, and diagnostics so no command-interface choice defines the core workflow.
- Version `config.json`, `state.json`, and generated YAML metadata. Validate and migrate every schema; settings must survive state reset or reconstruction.
- Define filename/path parsing, date and timezone utilities, structured error categories, scan locking, and atomic-write behavior.
- Build synthetic ISO-BMFF/QuickTime and filesystem fixtures alongside a separate redacted-golden-fixture mechanism.
- Provide offline test, lint, and formatting commands that never require real Voice Memos data.
- Ensure error reports and logs do not contain transcript text. Treat transcript content, source names, and absolute paths as sensitive diagnostic data by default.

### Exit criteria

- [x] A fresh checkout runs focused tests using only synthetic or redacted fixtures.
- [x] State, configuration, and output metadata schemas have explicit versions and tested migration/recovery behavior.
- [x] The scan lock and error taxonomy are testable independently of the CLI or `launchd`.

## Phase 3: File discovery and source metadata

### Goal

Find eligible recordings without altering Voice Memos and turn source facts into reliable, incremental candidates.

### Dependencies

Phase 2.

### Scope and decisions to validate

- Enumerate only `.m4a` and `.qta` within the configured source directory. Normalize filename case and parse date, time, format, and memo ID using a documented grammar.
- Use the filename memo ID as the normal deduplication identity. Detect malformed filenames and duplicate IDs; do not guess a replacement identity.
- Define how a filename’s local timestamp maps to date folders, import cutoffs, DST boundaries, and time-zone metadata. Do not invent a UTC offset when it is not available from the source.
- Capture inexpensive source metadata/fingerprints needed to identify new, changed, and stable files. Normal scans must not reopen successful, unchanged recordings.
- Snapshot first-run candidates. “New recordings only” means created after setup, not an old memo that completed iCloud download after setup. Date-cutoff inclusivity must be explicit in the user experience.
- Classify inaccessible, changing, malformed, ID-colliding, and delayed-download files for later retry and conflict handling.

### Exit criteria

- [ ] Discovery has no write, rename, delete, or database-modification path under Voice Memos storage.
- [ ] Candidate status is deterministic and carries sufficient factual information for retries and conflicts.
- [ ] Import modes remain correct when source delivery is delayed.

## Phase 4: Native transcript extraction and fidelity

### Goal

Extract only Apple’s existing transcript and render it faithfully, without substituting another transcription engine or introducing interpretation.

### Dependencies

Phases 1 through 3.

### Scope and decisions to validate

- Implement bounded container parsing for every verified `.m4a` and `.qta` layout, reading only necessary metadata regions rather than audio payloads.
- Preserve native Unicode, text order, and meaningful whitespace. If a readable rendering adds paragraph boundaries, retain raw native text as canonical and version the rendering behavior.
- Preserve native text runs, their available time ranges, and locale in the extraction model without assuming a run is a word, even if the initial Markdown view does not display every attribute.
- Classify blank text separately from absent, malformed, incomplete, inaccessible, and unsupported content.
- Prove through tests that no network call, speech-recognition fallback, or Voice Memos database access can occur.

### Exit criteria

- [x] Each supported layout produces the native transcript or a precise non-success classification.
- [x] A blank transcript cannot become a successful archive candidate.
- [x] Golden tests establish text fidelity, Unicode behavior, timing/locale preservation, and bounded failure on corrupted containers.

## Phase 5: Archive output, deduplication, and conflicts

### Goal

Create a self-describing Markdown archive safely and preserve historical records when source evidence is ambiguous or changes.

### Dependencies

Phases 3 and 4.

### Scope and decisions to validate

- Default the archive root to `~/Documents/Voice Memo Archive/`, allow the user to override it during command-line setup, and create the required `YYYY/MM/DD/` layout and deterministic Markdown filename from source facts. Write minimal factual YAML that safely represents arbitrary Unicode and punctuation.
- Write to a temporary file on the destination filesystem and atomically rename it. Never leave partial output or overwrite a completed archive during normal processing.
- Include the original source filename, recorded local time, memo ID, and source format. Keep metadata factual; do not add generated titles, summaries, tags, interpretations, or transcript-derived deduplication.
- Compare later source fingerprints and extracted transcript hashes with the completed archive. Treat changed transcript, changed source, and duplicate memo ID as visible conflicts.
- Never delete an archive merely because its source later disappears. Preserve the existing archive until a documented, explicit revision/update action is chosen.
- Provide archive inspection that can reconstruct successful processing state from front matter and identify malformed or orphaned archive entries.

### Exit criteria

- [x] Markdown output is self-describing, fact-only, and robust to YAML/Markdown boundary cases.
- [x] Interrupted writes cannot create a completed-looking partial archive.
- [x] Duplicate, changed, and missing source situations retain historical text and report an actionable conflict.
- [x] Archive metadata can rebuild successful operational state.

## Phase 6: Operational state, retries, and recovery

### Goal

Keep ordinary scans efficient while ensuring incomplete and failed recordings remain visible, retryable, and recoverable.

### Dependencies

Phases 2, 3, and 5.

### Scope and decisions to validate

- Maintain versioned operational state apart from settings through validated, atomic writes and a single-scan lock.
- Support `pending`, `processed`, `skipped_empty`, `skipped_no_transcript`, `failed`, `needs_attention`, `acknowledged`, and `conflict` states. Record memo ID, source filename, attempt count, times, next retry, and a factual, transcript-free reason.
- Require stability across scans before classifying a source as empty. Retry transient states with three spaced, increasing-delay opportunities; after that retain a `needs_attention` record rather than silently dropping or retrying indefinitely.
- Provide targeted and bulk manual retry, acknowledgment of a `needs_attention` item, and explicit full reconciliation. An acknowledgment suppresses automatic retries but retains the factual state until a manual retry, full rescan, or source-file change reopens it. Reconstruct processed status from archives when possible and recover from absent or corrupt `state.json` without losing user settings.
- Record scan-level auditing facts: schema version, start/end, result counts, and the most recent non-sensitive error.

### Exit criteria

- [x] Normal scans do not parse stable successful recordings again.
- [x] A transient, empty, or failed source cannot disappear silently from status.
- [x] Retry spacing, exhaustion, acknowledgment, manual retry, and source-stability behavior have automated coverage.
- [x] State recovery and archive reconciliation preserve configuration and archival records.

## Phase 7: Setup, automation, and diagnostics

### Goal

Make first-run choices and background behavior understandable, reliable, and repairable without JSON editing.

### Dependencies

Phase 6.

### Scope and decisions to validate

- Offer command-line source selection and an archive-destination prompt defaulting to `~/Documents/Voice Memo Archive/`, all/date/new-only initial import, a candidate-count preview, cancellation/resume, monitoring or scheduled mode, and supported scan intervals. Setup must disclose that a Documents destination may be iCloud Drive-synced according to the user’s macOS settings.
- Define idempotent user-level `launchd` installation. Treat periodic scan as the reliable fallback to folder events; coalesce repeated triggers and prevent overlap.
- Provide a command-line surface only: setup, scan now, status, targeted and bulk retry, acknowledgment, full rescan, archive verification, and `doctor` diagnostics. Background runs remain quiet during ordinary pending and retry states; `status` is the user-visible inbox for unresolved work.
- Ensure diagnostics check scheduler state, permission status, source availability, configuration, pending retries, conflicts, and needs-attention records without exposing transcript text.

### Exit criteria

- [x] Users see what initial import will consider before it begins.
- [x] Cancellation, restart, duplicate events, and login/restart behavior do not cause duplicate processing.
- [x] Status and doctor provide actionable, privacy-safe recovery guidance.

## Phase 8: Packaging, permissions, and privacy

### Goal

Deliver a secure, understandable macOS installation whose actual behavior meets the project’s local-first privacy promise.

### Dependencies

Phase 7.

### Scope and decisions to validate

- Choose the distribution form and package dependencies so users do not need a developer runtime. Document code signing and notarization requirements before public release.
- Validate Full Disk Access for the actual signed process. Diagnose missing access rather than reporting “no recordings.”
- Make no telemetry, analytics, remote crash reporting, or network call part of the product. Test this claim rather than merely documenting it.
- Explain that an archive destination selected by a user may itself be cloud-synced; document local-storage, FileVault, backup, upgrade, and uninstall behavior honestly.
- Uninstalling the service must not delete the user’s archive. Logs should omit transcript content and sensitive paths by default.

### Exit criteria

- [x] A clean macOS account can install and run the distribution without a developer runtime.
- [x] Permission failures are accurately diagnosed.
- [x] Network denial and log-redaction checks pass.
- [x] Public privacy, installation, upgrade, and uninstall documentation matches tested behavior.

## Phase 9: End-to-end verification and release readiness

### Goal

Prove the assembled product against the real macOS/iCloud lifecycle and prepare a transparent public release.

### Dependencies

All prior phases.

### Scope and decisions to validate

- Maintain a manual verification matrix for macOS, source-device transcript availability, language/region, real synced mono, stereo, and spatial `.m4a` and `.qta`, delayed download, missing transcript, empty source, source change, permission denial, service restart, acknowledgment, and state recovery. Real samples remain local and are never committed.
- Run the full automated suite, package smoke tests, clean-install test, and repository audit for private fixtures and unintended network dependencies.
- Review setup, normal workflow, recovery, privacy, support matrix, limitations, and removal documentation.
- Convert each verified defect or important gap into a new numbered task plan before release; do not hide it in release notes.

### Exit criteria

- [ ] At least one real synced `.m4a` and one real synced `.qta` complete the archive flow with their visible Apple transcript preserved.
- [ ] Expected non-success states are visible and repairable.
- [ ] No personal audio, transcript, title, identifier, or raw private note is tracked in Git.
- [ ] Release documentation and known limitations are ready for public review.

## Definition of done

- A signed/installable macOS distribution can perform setup, diagnose required access, and run unattended through `launchd`.
- It safely imports and incrementally archives eligible `.m4a` and `.qta` recordings without modifying Voice Memos data or uploading content.
- It creates no Markdown file for an empty, incomplete, or transcript-less recording, while preserving visible, retryable operational outcomes.
- It preserves successful archives across source disappearance, changed-source conflicts, and rebuildable-state recovery.
- Automated and real-recording end-to-end verification meet the Phase 9 exit criteria.

## Plan history

- 2026-09-08: Clarified the read-only, command-line-only product boundary: no Voice Memos database access, transcription fallback, or graphical app. Added verified-layout investigation for local `.m4a`/`.qta` samples; `status`, retry, and acknowledgment behavior; and the default archive root, `~/Documents/Voice Memo Archive/`.
- 2026-09-08: Chose Python as the implementation language/toolchain, ahead of Phase 2. Phase 8's "no developer runtime" install requirement means the eventual distribution must bundle its own interpreter (e.g. a frozen/py2app-style build) rather than relying on a system Python — record this as a Phase 8 constraint to revisit when packaging is scoped.
- 2026-09-08: Added Phase 0 so the committed public baseline, local-only privacy boundary, and detailed Phase 1 task plan are mandatory prerequisites for implementation.
- 2026-09-07: Consolidated initial technical scope from prematurely created future task files into this master roadmap. Detailed task files will be created only when their phase begins.
