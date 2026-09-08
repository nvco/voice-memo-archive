"""Command-line entry point.

Deliberately thin: each subcommand parses arguments and calls straight into
`scheduling`/`diagnostics`, so the workflow itself is never defined here —
`launchd` (Phase 7) will call the same underlying functions directly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / "Library/Application Support/Voice Memo Archive/config.json"
DEFAULT_STATE_PATH = Path.home() / "Library/Application Support/Voice Memo Archive/state.json"


def _cmd_scan(args: argparse.Namespace) -> int:
    from . import scheduling

    try:
        scheduling.run_scan(args.config, args.state)
    except NotImplementedError as exc:
        print(f"not yet implemented: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    print("not yet implemented: status reporting is added in Phase 6/7", file=sys.stderr)
    return 1


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import diagnostics

    try:
        diagnostics.check_recordings_access(args.recordings_source)
    except NotImplementedError as exc:
        print(f"not yet implemented: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-memo-archive")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="run one archive scan")
    scan_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    scan_parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    scan_parser.set_defaults(func=_cmd_scan)

    status_parser = subparsers.add_parser("status", help="show current archive status")
    status_parser.set_defaults(func=_cmd_status)

    doctor_parser = subparsers.add_parser("doctor", help="diagnose access/permission problems")
    doctor_parser.add_argument("--recordings-source", type=Path, dest="recordings_source")
    doctor_parser.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
