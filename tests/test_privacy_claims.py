"""Product-level proof of Phase 8's two claims-to-test:

- "no telemetry, analytics, remote crash reporting, or network call"
- "logs should omit transcript content... by default"

`tests/test_extraction.py` already proves the no-network claim for
`extraction.extract_transcript` alone; this file proves it across the
whole `cli.py` command surface instead, since that's the actual product
boundary a user invokes.
"""

import json
import socket
from pathlib import Path

import mp4_builders as mp4

from voice_memo_archive.archive import write_archive_entry
from voice_memo_archive.cli import main
from voice_memo_archive.config import load_config

TRANSCRIPT_MARKER = "SECRET-TRANSCRIPT-MARKER-9f3c2b7a"


def _write_synthetic_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    recordings_source = tmp_path / "recordings"
    archive_root = tmp_path / "archive"
    recordings_source.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": str(recordings_source),
                "archive_root": str(archive_root),
            }
        )
    )
    return config_path, recordings_source, archive_root


def _block_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must never open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_scan_never_opens_a_network_socket(tmp_path: Path, monkeypatch):
    config_path, recordings_source, _archive_root = _write_synthetic_project(tmp_path)
    (recordings_source / "20240115 143022-A.m4a").write_bytes(
        mp4.build_m4a_container(
            mp4.make_transcript_json(runs_texts=[TRANSCRIPT_MARKER], time_ranges=[[0.0, 1.0]])
        )
    )
    _block_sockets(monkeypatch)

    exit_code = main(
        ["scan", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )
    assert exit_code == 0


def test_status_doctor_verify_reconcile_never_open_a_network_socket(tmp_path: Path, monkeypatch):
    config_path, _recordings_source, _archive_root = _write_synthetic_project(tmp_path)
    state_path = tmp_path / "state.json"
    _block_sockets(monkeypatch)

    assert main(["status", "--state", str(state_path)]) == 0
    assert main(["doctor", "--config", str(config_path), "--state", str(state_path)]) == 0
    assert main(["verify", "--config", str(config_path)]) == 0
    assert main(["reconcile", "--config", str(config_path), "--state", str(state_path)]) == 0


def test_setup_never_opens_a_network_socket(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    recordings_source = tmp_path / "recordings"
    recordings_source.mkdir()
    _block_sockets(monkeypatch)

    exit_code = main(
        [
            "setup",
            "--config",
            str(tmp_path / "config.json"),
            "--state",
            str(tmp_path / "state.json"),
            "--recordings-source",
            str(recordings_source),
            "--yes",
        ]
    )
    assert exit_code == 0


def test_scan_output_never_contains_transcript_text(capsys, tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_synthetic_project(tmp_path)
    (recordings_source / "20240115 143022-A.m4a").write_bytes(
        mp4.build_m4a_container(
            mp4.make_transcript_json(runs_texts=[TRANSCRIPT_MARKER], time_ranges=[[0.0, 1.0]])
        )
    )
    state_path = tmp_path / "state.json"

    main(["scan", "--config", str(config_path), "--state", str(state_path)])
    out_err = capsys.readouterr()
    assert TRANSCRIPT_MARKER not in out_err.out
    assert TRANSCRIPT_MARKER not in out_err.err


def test_status_verify_output_never_contains_transcript_text(capsys, tmp_path: Path):
    config_path, recordings_source, archive_root = _write_synthetic_project(tmp_path)
    (recordings_source / "20240115 143022-A.m4a").write_bytes(
        mp4.build_m4a_container(
            mp4.make_transcript_json(runs_texts=[TRANSCRIPT_MARKER], time_ranges=[[0.0, 1.0]])
        )
    )
    state_path = tmp_path / "state.json"
    main(["scan", "--config", str(config_path), "--state", str(state_path)])
    capsys.readouterr()  # discard scan's own output

    main(["status", "--state", str(state_path)])
    out_err = capsys.readouterr()
    assert TRANSCRIPT_MARKER not in out_err.out
    assert TRANSCRIPT_MARKER not in out_err.err

    main(["verify", "--config", str(config_path)])
    out_err = capsys.readouterr()
    assert TRANSCRIPT_MARKER not in out_err.out
    assert TRANSCRIPT_MARKER not in out_err.err


def test_archive_file_itself_legitimately_contains_the_transcript(tmp_path: Path):
    # Sanity check for the two tests above: the marker really was
    # archived — its absence from CLI output is because CLI output never
    # touches transcript text, not because extraction/archiving silently
    # failed and there was nothing to leak in the first place.
    config_path, recordings_source, _archive_root = _write_synthetic_project(tmp_path)
    (recordings_source / "20240115 143022-A.m4a").write_bytes(
        mp4.build_m4a_container(
            mp4.make_transcript_json(runs_texts=[TRANSCRIPT_MARKER], time_ranges=[[0.0, 1.0]])
        )
    )
    main(["scan", "--config", str(config_path), "--state", str(tmp_path / "state.json")])
    archive_root = Path(load_config(config_path).archive_root)
    archived_text = "\n".join(p.read_text() for p in archive_root.rglob("*.md"))
    assert TRANSCRIPT_MARKER in archived_text


def test_doctor_output_never_contains_transcript_text(capsys, tmp_path: Path):
    config_path, _recordings_source, archive_root = _write_synthetic_project(tmp_path)
    metadata = {
        "recording_id": "REC-1",
        "source_filename": "a.m4a",
        "source_format": "m4a",
        "source_size": 1,
        "source_mtime": 1.0,
        "recorded_at": "2024-01-15T14:30:22-08:00",
        "locale": "en_US",
        "extraction_format_version": 1,
        "archived_at": "2024-01-15T20:00:00Z",
    }
    write_archive_entry(archive_root, metadata, TRANSCRIPT_MARKER)

    main(["doctor", "--config", str(config_path), "--state", str(tmp_path / "state.json")])
    out_err = capsys.readouterr()
    assert TRANSCRIPT_MARKER not in out_err.out
    assert TRANSCRIPT_MARKER not in out_err.err
