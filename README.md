# Voice Memo Archive

A privacy-first macOS command-line tool that exports Apple Voice Memos'
existing native transcripts into a durable, local Markdown archive.

The archive is the source of truth. This tool does **not** re-transcribe
audio, generate AI summaries, upload recordings, or modify Voice Memos
storage in any way. It only reads the transcript Apple already created and
writes it out as plain Markdown files, grouped by year/month/day, that you
own and can read with any text editor forever — independent of Apple, this
tool, or any particular app.

## Requirements

- macOS
- Python 3.11 or later, already installed (this tool doesn't bundle its
  own interpreter — see [Installation](#installation))
- Full Disk Access granted to whatever runs the tool (Terminal, or your
  Python interpreter) — macOS requires this even for read-only access to
  the Voice Memos recordings folder, and gives no automatic prompt for it.
  `voice-memo-archive doctor` will tell you clearly if this is missing.

## Installation

Clone the repository, then install it into a virtual environment:

```sh
git clone https://github.com/nvco/voice-memo-archive.git
cd voice-memo-archive
uv venv .venv
uv pip install -e ".[dev]" --python .venv/bin/python
```

(No `uv`? Plain `pip` works the same way: `python3.11 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"`.)

This installs the `voice-memo-archive` command inside `.venv`. Run it as
`.venv/bin/voice-memo-archive`, or activate the virtual environment first
(`source .venv/bin/activate`) and just use `voice-memo-archive`.

There is currently no signed, notarized, or App Store distribution — this
is a source install for people comfortable cloning a repository and
running a terminal command, not a double-click installer for a general
audience.

## Setup

```sh
voice-memo-archive setup
```

This walks you through:

- **Recordings source** — defaults to Apple's own Voice Memos folder.
- **Archive destination** — defaults to `~/Documents/Voice Memo Archive/`.
  If your destination is under `~/Documents`, `setup` will tell you it may
  be synced by iCloud Drive depending on your own System Settings — that's
  a fact about `~/Documents`, not something this tool controls.
- **Initial import scope** — `all` (every existing recording), `new_only`
  (nothing existing yet, only recordings made from today onward), or
  `date` (only recordings from a date you choose onward).

`setup` shows you exactly how many recordings the initial import will
consider *before* anything is written, and asks for confirmation unless
you pass `--yes`. It writes your choices to `config.json`. There is no
background automation of any kind — this tool never registers anything
with `launchd`, cron, or any other scheduler, and nothing runs unless you
run it. Pull in new recordings any time with `scan` (see below); a shell
alias or an occasional habit is all the "automation" this tool offers.

## Everyday use

```sh
voice-memo-archive scan       # run one scan now, pulling in anything new
voice-memo-archive status     # what's archived, what needs attention
voice-memo-archive doctor     # diagnose access/permission problems
```

If something needs your attention (a recording that failed repeatedly, or
a genuine conflict), `status` lists it by name with a factual reason —
never with any transcript content. You can:

```sh
voice-memo-archive retry --id <recording-id>   # retry one recording now
voice-memo-archive retry --all                 # retry everything needing attention
voice-memo-archive acknowledge --id <recording-id>   # quiet it without retrying
voice-memo-archive verify                      # check the archive tree for problems
voice-memo-archive reconcile                   # rebuild tracking state from the archive itself
```

## Privacy

- **No network calls of any kind** — no telemetry, no analytics, no crash
  reporting, nothing. This is proven by an automated test
  (`tests/test_privacy_claims.py`), not just documented.
- **No transcript content ever appears in this tool's own output** — not
  in `scan`/`status`/`doctor` output, not in logs. Also proven by an
  automated test, not just a convention this tool tries to follow.
- **Voice Memos storage is never modified.** Every read is read-only; the
  Voice Memos database itself is never touched, only the recordings
  folder and the files in it.
- Your archive destination may itself be synced by iCloud Drive, Time
  Machine, or any other backup you already have configured — this tool
  doesn't add or change that, it just writes plain files to a folder you
  chose.

## Uninstalling

There is no background service to uninstall — everything this tool does
happens only while a command is actually running. To remove it entirely:

```sh
rm "$HOME/Library/Application Support/Voice Memo Archive/config.json" \
   "$HOME/Library/Application Support/Voice Memo Archive/state.json"
```

(Optional, and only your settings/internal bookkeeping — never your
archive; easy to lose and easy to regenerate by running `setup` again.)
Then delete the `.venv` you created during installation, and the cloned
repository if you don't plan to use it again. **Your archived Markdown
files are untouched by any of this** — nothing above ever reads or writes
your archive location.

## Known limitations

- Distribution is source-only (git clone + `pip install`), which means
  Python must already be installed — there's currently no standalone,
  signed, dependency-free installer.
- Every non-`ok` extraction/archive outcome (malformed container, empty
  transcript, source conflicts, etc.) is covered by automated tests
  against synthetic recordings, but full verification against real,
  varied `.m4a`/`.qta` files across every real-world condition is
  ongoing.
