"""Command-line entry point.

Deliberately thin: each subcommand parses arguments and calls straight into
`setup`/`scheduling`/`archive`/`diagnostics`/`launchd`, so the workflow
itself is never defined here — `launchd`'s own scheduled invocation calls
the same `scan` entry point directly, not a second copy of its logic.

`setup` writes the `launchd` plist unconditionally (safe — it's just a
file) but only ever actually registers it with the running `launchd`
(`launchd.bootstrap`, a real, persistent system change) behind `--yes`/
`--enable-now` and an interactive confirmation otherwise — see
`tasks/035-...md` for why this is deliberately more cautious than
"idempotent installation" alone might suggest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / "Library/Application Support/Voice Memo Archive/config.json"
DEFAULT_STATE_PATH = Path.home() / "Library/Application Support/Voice Memo Archive/state.json"


def _cmd_scan(args: argparse.Namespace) -> int:
    from . import scheduling
    from .errors import ArchiveError

    try:
        summary = scheduling.run_scan(args.config, args.state, force=args.force)
    except ArchiveError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    counts = ", ".join(
        f"{status}={count}" for status, count in sorted(summary.result_counts.items())
    )
    print(f"scan complete: {counts or 'nothing to do'}")
    for entry in summary.unidentified:
        print(f"unidentified ({entry.status}): {entry.path}", file=sys.stderr)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from .errors import StateError
    from .state import RecordingStatus, load_state

    try:
        state = load_state(args.state)
    except StateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for record in state.recordings.values():
        counts[record.status.value] = counts.get(record.status.value, 0) + 1

    print("Status by recording:")
    if counts:
        for status, count in sorted(counts.items()):
            print(f"  {status}: {count}")
    else:
        print("  (nothing tracked yet)")

    last_completed = state.last_scan_completed_at or "-"
    print(f"Last scan: {state.last_scan_started_at or 'never'} -> {last_completed}")
    if state.last_scan_last_error:
        print(f"Last scan error category: {state.last_scan_last_error}")

    inbox_statuses = (RecordingStatus.NEEDS_ATTENTION, RecordingStatus.CONFLICT)
    inbox = sorted(
        (rid, record) for rid, record in state.recordings.items() if record.status in inbox_statuses
    )
    if inbox:
        print("Needs your attention:")
        for recording_id, record in inbox:
            print(
                f"  {recording_id} [{record.status.value}] "
                f"{record.source_filename or ''} — "
                f"{record.last_error_category or 'unknown reason'} "
                f"(attempts: {record.retry_count})"
            )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import diagnostics

    results = diagnostics.run_doctor(config_path=args.config, state_path=args.state)
    all_ok = True
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")
        all_ok = all_ok and result.ok
    return 0 if all_ok else 1


def _cmd_retry(args: argparse.Namespace) -> int:
    from . import scheduling
    from .state import load_state, save_state

    state = load_state(args.state)
    try:
        if args.all:
            updated = scheduling.retry_all_needing_attention(state)
        else:
            updated = scheduling.retry(state, args.id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    save_state(args.state, updated)
    print("Retry scheduled — run `scan` to act on it.")
    return 0


def _cmd_acknowledge(args: argparse.Namespace) -> int:
    from . import scheduling
    from .state import load_state, save_state

    state = load_state(args.state)
    try:
        updated = scheduling.acknowledge(state, args.id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    save_state(args.state, updated)
    print(f"Acknowledged {args.id}.")
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    from . import config, scheduling
    from .errors import StateError
    from .state import State, load_state, save_state

    cfg = config.load_config(args.config)
    archive_root = Path(cfg.archive_root).expanduser()
    try:
        state = load_state(args.state)
    except StateError:
        state = State()
    reconciled = scheduling.reconcile_with_archive(state, archive_root)
    save_state(args.state, reconciled)
    print(f"Reconciled against the archive — {len(reconciled.recordings)} recording(s) tracked.")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from . import archive, config
    from .paths import redact_home_path

    cfg = config.load_config(args.config)
    archive_root = Path(cfg.archive_root).expanduser()
    inspection = archive.inspect_archive(archive_root)
    print(
        f"entries={len(inspection.entries)} "
        f"malformed={len(inspection.malformed)} "
        f"orphaned={len(inspection.orphaned)}"
    )
    for entry in inspection.malformed:
        print(f"  malformed: {redact_home_path(entry.path)} — {entry.reason}", file=sys.stderr)
    for path in inspection.orphaned:
        print(f"  orphaned: {redact_home_path(path)}", file=sys.stderr)
    return 0 if not inspection.malformed and not inspection.orphaned else 1


def _prompt_text(label: str, default: str) -> str:
    answer = input(f"{label} [{default}]: ").strip()
    return answer or default


def _prompt_choice(label: str, default: str, choices: list[str]) -> str:
    options = "/".join(choices)
    while True:
        answer = input(f"{label} ({options}) [{default}]: ").strip()
        if not answer:
            return default
        if answer in choices:
            return answer
        print(f"Please enter one of: {options}")


def _prompt_date(label: str, default: str | None) -> str:
    from datetime import date

    default_suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{label} (YYYY-MM-DD){default_suffix}: ").strip()
        candidate = answer or default
        if not candidate:
            print("A date is required when import mode is 'date'.")
            continue
        try:
            date.fromisoformat(candidate)
        except ValueError:
            print("Please enter a date as YYYY-MM-DD.")
            continue
        return candidate


def _prompt_int(label: str, default: int, suggestions: tuple[int, ...]) -> int:
    options = "/".join(str(s) for s in suggestions)
    while True:
        answer = input(f"{label} ({options}) [{default}]: ").strip()
        if not answer:
            return default
        try:
            return int(answer)
        except ValueError:
            print("Please enter a whole number of seconds.")


def _format_setup_menu(values: dict[str, object]) -> str:
    since = values["import_since"] or "(not set)"
    if values["import_mode"] != "date":
        since = f"{since} — unused unless import mode is 'date'"
    return "\n".join(
        [
            "Current setup:",
            f"  1) Recordings source      {values['recordings_source']}",
            f"  2) Archive destination    {values['archive_root']}",
            f"  3) Import mode            {values['import_mode']}",
            f"  4) Import since date      {since}",
            f"  5) Schedule mode          {values['schedule_mode']}",
            f"  6) Scan interval          {values['scan_interval_seconds']}s",
        ]
    )


def _ensure_import_since(values: dict[str, object]) -> None:
    if values["import_mode"] == "date" and not values["import_since"]:
        values["import_since"] = _prompt_date("Import since date", None)


def _edit_setup_menu(values: dict[str, object]) -> None:
    """Show every setting with its current value; let the user pick one by
    number to change, repeating until they press Enter to continue. Replaces
    the old fixed-order sequential wizard (tasks/035-...md) so all settings
    are visible and editable at once instead of one at a time.
    """
    from . import config

    while True:
        print(_format_setup_menu(values))
        choice = input("Enter a number to change a setting, or press Enter to continue: ").strip()
        if not choice:
            return
        if choice == "1":
            values["recordings_source"] = _prompt_text(
                "Recordings source", str(values["recordings_source"])
            )
        elif choice == "2":
            values["archive_root"] = _prompt_text(
                "Archive destination", str(values["archive_root"])
            )
        elif choice == "3":
            values["import_mode"] = _prompt_choice(
                "Import mode", str(values["import_mode"]), sorted(config.IMPORT_MODES)
            )
            _ensure_import_since(values)
        elif choice == "4":
            values["import_since"] = _prompt_date(
                "Import since date",
                values["import_since"],  # type: ignore[arg-type]
            )
        elif choice == "5":
            values["schedule_mode"] = _prompt_choice(
                "Schedule mode", str(values["schedule_mode"]), sorted(config.SCHEDULE_MODES)
            )
        elif choice == "6":
            values["scan_interval_seconds"] = _prompt_int(
                "Scan interval seconds",
                int(values["scan_interval_seconds"]),
                config.SUPPORTED_SCAN_INTERVALS_SECONDS,
            )
        else:
            print("Please enter one of: 1, 2, 3, 4, 5, 6")


def _cmd_setup(args: argparse.Namespace) -> int:
    from . import config, launchd, setup
    from .errors import ArchiveError, ConfigError

    try:
        existing = config.load_config(args.config)
    except ConfigError as exc:
        print(
            f"Warning: existing config.json could not be read ({exc}); using defaults.",
            file=sys.stderr,
        )
        existing = config.Config()

    # An omitted flag falls back to the current config value (or the package
    # default when no config exists yet — `load_config` already returns
    # `Config()` in that case), never to a hardcoded default outright. This
    # is what makes `setup --yes --scan-interval 300` a safe way to change
    # one setting without restating every other one, and it's what seeds the
    # interactive menu below with the right starting point.
    resolved_import_mode = args.import_mode or existing.import_mode
    existing_import_since = existing.import_since if existing.import_mode == "date" else None
    values: dict[str, object] = {
        "recordings_source": (
            str(args.recordings_source) if args.recordings_source else existing.recordings_source
        ),
        "archive_root": (str(args.archive_root) if args.archive_root else existing.archive_root),
        "import_mode": resolved_import_mode,
        "import_since": (
            args.import_since
            if args.import_since is not None
            else (existing_import_since if resolved_import_mode == "date" else None)
        ),
        "schedule_mode": args.schedule_mode or existing.schedule_mode,
        "scan_interval_seconds": (
            args.scan_interval if args.scan_interval is not None else existing.scan_interval_seconds
        ),
    }

    if not args.yes:
        # Interactive: a menu of every setting and its current value (seeded
        # above from flags/existing config/package defaults), editable by
        # number, in any order, as many times as wanted. See tasks/035-...md.
        _ensure_import_since(values)
        _edit_setup_menu(values)

    try:
        plan = setup.build_setup_plan(
            recordings_source=str(values["recordings_source"]),
            archive_root=str(values["archive_root"]),
            import_mode=str(values["import_mode"]),
            import_since=values["import_since"],  # type: ignore[arg-type]
            schedule_mode=str(values["schedule_mode"]),
            scan_interval_seconds=int(values["scan_interval_seconds"]),
        )
    except ValueError as exc:
        print(f"invalid setup options: {exc}", file=sys.stderr)
        return 1
    except ArchiveError as exc:
        # The candidate-count preview inside build_setup_plan reads the
        # recordings folder (discovery.scan) before anything is written; a
        # missing/unreadable source must fail cleanly here, the same way
        # `scan` itself does, rather than surfacing a raw traceback.
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Recordings source: {plan.recordings_source}")
    print(f"Archive destination: {plan.archive_root}")
    if plan.archive_root_may_sync:
        print(
            "Note: this destination is under ~/Documents, which may be "
            "synced by iCloud Drive depending on your System Settings."
        )
    since_note = f" (since {plan.import_since})" if plan.import_since else ""
    print(f"Import mode: {plan.import_mode}{since_note}")
    print(f"Initial import will consider {plan.candidate_preview_count} recording(s).")
    print(f"Schedule: {plan.schedule_mode}, every {plan.scan_interval_seconds}s")

    if not args.yes:
        answer = input("Proceed with this setup? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Setup cancelled; nothing was changed.")
            return 0

    committed = setup.commit_setup(args.config, plan)
    print(f"Wrote {args.config}")

    plist_path = launchd.install(
        config_path=args.config,
        state_path=args.state,
        recordings_source=Path(committed.recordings_source).expanduser(),
        schedule_mode=committed.schedule_mode,
        scan_interval_seconds=committed.scan_interval_seconds,
    )
    print(f"Wrote {plist_path}")

    manual_hint = f"launchctl bootstrap gui/$(id -u) {plist_path}"
    if args.enable_now:
        enable = args.yes
        if not enable:
            answer = input("Enable background automation now? [y/N] ").strip().lower()
            enable = answer in ("y", "yes")
        if enable:
            launchd.bootstrap(plist_path)
            print("Background automation enabled.")
        else:
            print(f"Not enabled. Enable later with: {manual_hint}")
    else:
        print(f"Background automation not enabled. Enable later with: {manual_hint}")

    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove the background service. Never touches the archive tree.

    Per `tasks/000-initial-build.md` Phase 8: "Uninstalling the service
    must not delete the user's archive." This command has no code path
    that reads `archive_root` at all, let alone writes to it — not a
    redaction, a structural guarantee.
    """
    from . import launchd

    launchd.bootout()  # safe/no-op if nothing was ever registered
    plist_path = launchd.plist_path()
    if plist_path.exists():
        plist_path.unlink()
        print(f"Removed {plist_path}")
    else:
        print("No launchd job was installed.")

    if args.purge_config:
        for path in (args.config, args.state):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")

    print("Your archive was not touched and remains at its configured location.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import config

    parser = argparse.ArgumentParser(prog="voice-memo-archive")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_config_state_args(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
        subparser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)

    scan_parser = subparsers.add_parser("scan", help="run one archive scan")
    add_config_state_args(scan_parser)
    scan_parser.add_argument(
        "--force",
        action="store_true",
        help="re-verify every recording against its source, even ones already processed",
    )
    scan_parser.set_defaults(func=_cmd_scan)

    status_parser = subparsers.add_parser("status", help="show current archive status")
    add_config_state_args(status_parser)
    status_parser.set_defaults(func=_cmd_status)

    doctor_parser = subparsers.add_parser("doctor", help="diagnose access/permission problems")
    add_config_state_args(doctor_parser)
    doctor_parser.set_defaults(func=_cmd_doctor)

    retry_parser = subparsers.add_parser("retry", help="retry a failed/needs-attention recording")
    add_config_state_args(retry_parser)
    retry_group = retry_parser.add_mutually_exclusive_group(required=True)
    retry_group.add_argument("--id", dest="id", help="retry this recording ID")
    retry_group.add_argument(
        "--all", action="store_true", help="retry every needs_attention recording"
    )
    retry_parser.set_defaults(func=_cmd_retry)

    acknowledge_parser = subparsers.add_parser(
        "acknowledge", help="acknowledge a needs_attention recording"
    )
    add_config_state_args(acknowledge_parser)
    acknowledge_parser.add_argument("--id", dest="id", required=True)
    acknowledge_parser.set_defaults(func=_cmd_acknowledge)

    reconcile_parser = subparsers.add_parser(
        "reconcile", help="rebuild processed status from the archive tree"
    )
    add_config_state_args(reconcile_parser)
    reconcile_parser.set_defaults(func=_cmd_reconcile)

    verify_parser = subparsers.add_parser(
        "verify", help="check the archive tree for malformed/orphaned files"
    )
    verify_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    verify_parser.set_defaults(func=_cmd_verify)

    setup_parser = subparsers.add_parser(
        "setup", help="configure source, destination, and schedule"
    )
    add_config_state_args(setup_parser)
    # No `default=` on any of these (beyond argparse's implicit None): an
    # omitted flag must be distinguishable from an explicitly-chosen value,
    # so `_cmd_setup` can prompt for it interactively instead of silently
    # substituting a hardcoded default. `choices` still validates a value
    # given explicitly; it does not apply to the None default itself.
    setup_parser.add_argument("--recordings-source", type=Path, dest="recordings_source")
    setup_parser.add_argument("--archive-root", type=Path, dest="archive_root")
    setup_parser.add_argument(
        "--import-mode",
        choices=sorted(config.IMPORT_MODES),
        default=None,
        dest="import_mode",
    )
    setup_parser.add_argument("--import-since", dest="import_since")
    setup_parser.add_argument(
        "--schedule-mode",
        choices=sorted(config.SCHEDULE_MODES),
        default=None,
        dest="schedule_mode",
    )
    setup_parser.add_argument(
        "--scan-interval",
        type=int,
        choices=list(config.SUPPORTED_SCAN_INTERVALS_SECONDS),
        default=None,
        dest="scan_interval",
    )
    setup_parser.add_argument(
        "--yes", action="store_true", help="skip confirmation prompts (for scripted use)"
    )
    setup_parser.add_argument(
        "--enable-now",
        action="store_true",
        dest="enable_now",
        help="also register the scan job with launchd immediately",
    )
    setup_parser.set_defaults(func=_cmd_setup)

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="remove the background service (never touches the archive)"
    )
    add_config_state_args(uninstall_parser)
    uninstall_parser.add_argument(
        "--purge-config",
        action="store_true",
        dest="purge_config",
        help="also remove config.json/state.json (settings/bookkeeping only, never the archive)",
    )
    uninstall_parser.set_defaults(func=_cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
