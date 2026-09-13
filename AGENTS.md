# Voice Memo Archive — Agent Guide

**This is the single source of truth.** 
All agents should read and update this file.

## Purpose

Voice Memo Archive is a privacy-first macOS utility that exports Apple Voice Memos’ existing native transcripts into a durable Markdown archive. The archive is the source of truth by default, and stays that way unless the user explicitly runs `empty` (see the invariant below) — this tool supports both "keep the archive permanently" and "use it as a temporary staging area before importing elsewhere" as equally valid usage patterns. This project does not re-transcribe audio, generate AI summaries, upload recordings, or modify Voice Memos storage.

## Decision context

This project exists so people retain a private, durable, app-independent copy
of the transcript Apple already created for their own recordings. When a
requirement is incomplete or values conflict, favor transcript fidelity, data
preservation, privacy, and transparent recovery over automation, convenience,
or clever interpretation. Surface uncertainty and unsupported cases rather
than silently changing, discarding, or replacing source material.

## Working method

1. Before substantial implementation work, read the relevant task plan in `tasks/`.
2. Complete work in the documented order unless a verified technical reason requires a change.
3. Keep each change scoped to the active task plan.
4. Add and run the relevant automated tests as the component is built.
5. Check a task-plan checkbox only after its implementation and stated verification are complete.
6. If new work, a defect, or an important edge case is discovered, add it to the current task plan or create a new numbered task-plan file before treating it as complete.
7. Record any material deviation from the plan in the relevant task-plan file.

## Project invariants

- Treat Voice Memos storage as read-only.
- Do not access the private Voice Memos database; inspect the configured recordings folder and recording containers only.
- Support both `.m4a` and `.qta` recordings.
- Extract Apple’s existing native transcript; do not use a replacement transcription service.
- Keep processing local: do not make network calls, upload recordings or transcripts, or add telemetry. A user-selected archive destination may be synchronized by their own macOS services.
- Create Markdown files grouped by recording year, month, and day.
- Use the Voice Memo filename’s unique ID as the primary deduplication key.
- Keep generated YAML metadata factual. Do not add AI-generated summaries, titles, tags, or interpretations to the source archive.
- Use `config.json` for user settings and `state.json` for operational state, retry tracking, and scan history.
- Do not create archive files for empty or transcript-less recordings.
- `scan` never deletes an archive entry, for any reason. The only way to remove archived transcripts is the explicit, separately user-invoked `empty` command (see `tasks/051-empty-archive-command.md`) — never a side effect of scanning, setup, or any other command.
- Provide a command-line interface only; do not add a separate graphical application. Every run is a one-shot, user-invoked `scan` — there is no background/scheduled automation (removed; see `tasks/050-remove-background-automation.md`).

## Development setup

The implementation is Python (chosen in `tasks/000-initial-build.md`'s Plan
history). From a fresh checkout:

```
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
```

Then, offline and without any real Voice Memos data:

```
.venv/bin/python -m pytest -q   # tests
.venv/bin/ruff check .          # lint
.venv/bin/ruff format .         # format
```

## Testing and verification

- Add tests for every meaningful behavior change.
- Use only synthetic or redacted fixtures. Never commit personal audio files or transcripts.
- Run focused automated tests during implementation.
- Do not consider the project complete without end-to-end verification using real synced `.m4a` and `.qta` recordings.

## Shared skills

- The canonical source for reusable project skills is `skills/` at the repository root.
- Store each skill as `skills/<skill-name>/SKILL.md`, with optional scripts, references, templates, or assets alongside it.
- Do not duplicate a skill’s contents into tool-specific folders such as `.claude/` or `.codex/`.
- When a task matches a project skill, read and follow the corresponding `SKILL.md` before acting.
- If an agent requires a native discovery path, use compatibility symlinks from `.agents/skills` or `.claude/skills` to the root `skills/` folder. These entries are directory pointers only: they contain no skill files of their own and are not second sources of truth.

## Repository hygiene

- **Never run `git commit` without the user's explicit, in-the-moment approval of that specific commit.** Staging changes, drafting a commit message, and showing the user what would be committed is fine; running `git commit` itself is not, until the user says yes to that commit. A prior request to do related work (e.g. "continue the task," "document this finding") is not approval to commit — approval must be given for the commit itself, every time. This applies to every agent working in this repository, not just one session.
- `tasks/` is committed project history. Keep task plans current and their checkboxes accurate.
- Add a `CHANGELOG.md` entry (Keep a Changelog format, under `Unreleased` until there is a release) when a phase or other meaningful change completes. Keep entries short and factual — summarize outcomes rather than restating a task plan's own history or a task file's material-deviation notes.
- `resources/` is a tracked folder for polished public planning material and other curated project resources. Do not place raw private notes there.
- Keep public documentation user-facing and concise. Do not publish private research notes or raw working material.
