# Future idea: sample AI-summary skill over the archive

Not part of the original 9-phase roadmap in `tasks/000-initial-build.md` —
deliberately not given a phase number (see `AGENTS.md`'s "Shared skills"
section instead). Recorded here per the user's explicit request
(2026-09-10) so it isn't lost, and deliberately **not started** — the
user asked to note it and return to finishing Phase 9 first.

## The idea

A sample skill (`skills/voice-memo-summary/SKILL.md` or similar), living
alongside this project's existing `skills/wrap-up/`, that a user can point
their own AI assistant of choice at (Claude, ChatGPT, a local model —
whatever they already trust) to read the *already-archived* Markdown
files and produce a summary or action-item list. This stays completely
separate from the core CLI and archiving pipeline — the archiving tool's
job stops at "durable, private, plain-text copy exists on disk"; this
skill would be an optional, downstream, user-invoked consumer of that
archive, not something `scan`/`setup`/etc. ever calls. Matches this
project's explicit "no AI-generated summaries" invariant for the *archive
itself* — the summary is a separate artifact the user asks for, on their
own terms, with their own AI tool, not something baked into the archive
or generated automatically.

Requested variants (2026-09-10), as a starting menu, not necessarily
exhaustive:

- Summarize the day
- Summarize the week
- Summarize the latest (however "latest" ends up being defined — see
  below)
- "and so on" — the user expects more variants to be added over time; the
  skill should be structured so adding one is easy (a consistent
  date-range-in, summary-out shape), not a one-off script per variant.

## Design question raised, and the recommended answer

The user asked: how does the skill know how far back to go, and won't
asking for "the week" after already asking for "the day" re-summarize
the same day twice — is that a problem to solve?

**Recommendation: no tracking, no "last run" state — keep it stateless.**

- The archive's `.md` files are immutable once written (Phase 5's own
  design). Re-reading a handful of them for an overlapping range costs
  nothing meaningful — this isn't like `scan` avoiding re-extraction of
  an unchanged recording, where the work being skipped is genuinely
  expensive/redundant.
- A "day" summary and a "week" summary are answers to two different
  questions, not two runs of the same job — a week summary *should*
  naturally include a day that was already summarized alone. That's
  correct overlap, not accidental duplication to prevent.
- Each invocation should just take an explicit range (a specific date, a
  specific week, or a plain-language range the user states in the
  moment, like "since Tuesday") and read whatever archive files fall
  in it. If a user wants "only what's new since we last talked," that's
  better served by them saying the actual cutoff in the request than by
  the skill secretly persisting a "last summarized at" timestamp
  somewhere — the latter adds a real state-management surface (a new
  file, concurrency/staleness questions, "what does latest even mean
  across multiple parallel conversations") for a problem this mostly
  doesn't have.
- If "summarize the latest" specifically needs a concrete, reproducible
  definition (rather than "since we last spoke," which is
  conversation-scoped and needs no tracking at all), the simplest
  grounded definition is probably "the most recent single day that has
  at least one archived recording" — computed fresh each time by looking
  at the archive tree's own `YYYY/MM/DD` structure, not from any
  separately tracked state.

## Status

Not started. Revisit after Phase 9 (`tasks/045-...md`) is complete.
