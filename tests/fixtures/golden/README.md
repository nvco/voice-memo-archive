# Golden fixtures

Redacted fixtures kept separate from `../synthetic/` because they exist to
catch drift against real container/schema shapes discovered by inspecting
actual samples (see `tasks/005-platform-feasibility-and-data-contract.md`),
not to be authored freely like the synthetic ones.

Nothing here yet. Per `AGENTS.md`, only non-sensitive structural facts may
ever be committed — never real transcript text, titles, or raw sample
bytes. If a fixture is derived from a real sample's structure, redact its
content-bearing fields before committing (e.g. replace real transcript
strings with placeholder text) and note the redaction in the commit that
adds it.
