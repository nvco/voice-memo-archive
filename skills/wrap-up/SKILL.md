---
name: wrap-up
description: End-of-session checkpoint. Updates the active task file's Status section, verifies logged work actually happened, checks off satisfied checkboxes, and stages a commit — so a fresh session (or another agent) knows exactly where to continue.
---

# Wrap-up

Run this when the user signals they're pausing or ending a session (e.g. they
type `/wrap-up`, or say something like "let's stop here," "I'm closing this
session"). The goal: leave the repository in a state where a brand-new
session, with no memory of this conversation, can read one file and know
exactly what's done and what to do next.

## Steps

1. **Identify the active task file(s).** Usually the task file(s) under
   `tasks/` that were read or edited in this session. If more than one phase
   was touched, or it's not obvious, ask rather than guess.

2. **Verify before writing.** For every claim you're about to write down as
   "done" — a check run, a file inspected, a decision reached — confirm it
   actually happened in this session (re-read the relevant tool output or
   the file itself) rather than trusting your own summary. Do not write
   "logged" or "done" for anything you haven't actually verified is on disk.
   (This skill exists partly because that mistake happened once already —
   don't repeat it.)

3. **Update the task file's `Status` section** (add one if the file doesn't
   have one yet, following the pattern in `tasks/005-platform-feasibility-and-data-contract.md`):
   - `Done`: what was actually completed and verified this session.
   - `Not done yet — next action`: what remains, phrased as a concrete next
     step a fresh session can act on immediately — not just "continue
     investigation."
   - Update the `_Last updated: <date>_` line.

4. **Reconcile checkboxes.** Check off any scope/exit-criteria checkboxes
   that are now genuinely satisfied and verified; leave everything else
   unchecked. Per `AGENTS.md`'s working method, never check a box on
   intention alone.

5. **Make sure supporting sections are current.** If the task file has
   Session log / Findings / Deviations sections, confirm everything
   discussed this session is actually written into them, not just described
   in chat.

6. **Add a `CHANGELOG.md` entry** if a phase or other meaningful change
   completed this session, per the repository-hygiene rule in `AGENTS.md`.
   Skip this if nothing meaningful shipped this session (e.g. pure
   investigation with no phase completed) — the task file's Status section
   already covers in-progress work.

7. **Review the diff.** Run `git status` and `git diff` to see everything
   changed this session. Confirm nothing under `.local/`, no real recordings,
   transcript text, or other private material is staged.

8. **Stage and propose a commit.** Stage the relevant files, show the user
   the exact diff/file list and a proposed commit message, and **stop for
   their explicit go-ahead before running `git commit`** — this skill never
   commits without that confirmation.

9. **Close with a short summary** in chat: what got done this session, what
   the immediate next action is, and confirmation of what was (or wasn't)
   committed. Keep it to a few lines — the task file is the source of truth,
   this is just a pointer to it.
