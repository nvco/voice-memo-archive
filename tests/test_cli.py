import json
from pathlib import Path

from voice_memo_archive import launchd
from voice_memo_archive.archive import write_archive_entry
from voice_memo_archive.cli import build_parser, main
from voice_memo_archive.io_utils import ScanLock
from voice_memo_archive.state import RecordingState, RecordingStatus, State, save_state

ARCHIVE_METADATA = {
    "recording_id": "AAAAAAAA-1111-2222-3333-444444444444",
    "source_filename": "20240115 143022-AAAAAAAA-1111-2222-3333-444444444444.m4a",
    "source_format": "m4a",
    "source_size": 100,
    "source_mtime": 123.0,
    "recorded_at": "2024-01-15T14:30:22-08:00",
    "locale": "en_US",
    "extraction_format_version": 1,
    "archived_at": "2024-01-15T20:00:00Z",
}


def _write_synthetic_config(tmp_path):
    # Never rely on cli.py's real Application-Support defaults in a test —
    # those point at the real Voice Memos folder on whatever machine runs
    # this suite. Every test gets its own empty, synthetic tree.
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
    return config_path


def test_scan_with_no_recordings_reports_nothing_to_do(capsys, tmp_path):
    config_path = _write_synthetic_config(tmp_path)
    exit_code = main(
        ["scan", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )
    assert exit_code == 0
    assert "nothing to do" in capsys.readouterr().out


def test_scan_blocked_by_a_concurrent_scan_fails_cleanly_not_duplicated(capsys, tmp_path):
    # Phase 7 exit criterion: "duplicate events... do not cause duplicate
    # processing." Two overlapping triggers (e.g. WatchPaths + StartInterval
    # firing close together) must not both run a scan concurrently — the
    # second one refuses cleanly rather than racing the first.
    config_path = _write_synthetic_config(tmp_path)
    state_path = tmp_path / "state.json"
    lock = ScanLock(state_path.parent / "scan.lock")
    lock.acquire()
    try:
        exit_code = main(["scan", "--config", str(config_path), "--state", str(state_path)])
    finally:
        lock.release()
    assert exit_code == 1
    assert "scan_lock_held" in capsys.readouterr().err


def test_doctor_reports_ok_on_a_clean_synthetic_setup(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda: None)
    config_path = _write_synthetic_config(tmp_path)
    exit_code = main(
        ["doctor", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[OK] config" in out
    assert "[OK] recordings_source" in out


def test_status_with_no_state_reports_nothing_tracked(capsys, tmp_path):
    exit_code = main(["status", "--state", str(tmp_path / "state.json")])
    assert exit_code == 0
    assert "nothing tracked yet" in capsys.readouterr().out


def test_status_lists_needs_attention_records(capsys, tmp_path):
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        State(
            recordings={
                "REC-1": RecordingState(
                    status=RecordingStatus.NEEDS_ATTENTION,
                    source_filename="a.m4a",
                    last_error_category="transcript_malformed",
                    retry_count=3,
                )
            }
        ),
    )
    exit_code = main(["status", "--state", str(state_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "needs_attention: 1" in out
    assert "REC-1" in out
    assert "transcript_malformed" in out


def test_retry_requires_id_or_all():
    parser = build_parser()
    try:
        parser.parse_args(["retry"])
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass


def test_retry_by_id_moves_needs_attention_to_pending(capsys, tmp_path):
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        State(recordings={"REC-1": RecordingState(status=RecordingStatus.NEEDS_ATTENTION)}),
    )
    exit_code = main(["retry", "--state", str(state_path), "--id", "REC-1"])
    assert exit_code == 0
    from voice_memo_archive.state import load_state

    assert load_state(state_path).recordings["REC-1"].status == RecordingStatus.PENDING


def test_retry_unknown_id_fails_cleanly(capsys, tmp_path):
    state_path = tmp_path / "state.json"
    save_state(state_path, State())
    exit_code = main(["retry", "--state", str(state_path), "--id", "does-not-exist"])
    assert exit_code == 1
    assert capsys.readouterr().err


def test_acknowledge_moves_needs_attention_to_acknowledged(tmp_path):
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        State(recordings={"REC-1": RecordingState(status=RecordingStatus.NEEDS_ATTENTION)}),
    )
    exit_code = main(["acknowledge", "--state", str(state_path), "--id", "REC-1"])
    assert exit_code == 0
    from voice_memo_archive.state import load_state

    assert load_state(state_path).recordings["REC-1"].status == RecordingStatus.ACKNOWLEDGED


def test_reconcile_rebuilds_processed_from_the_archive(capsys, tmp_path):
    config_path = _write_synthetic_config(tmp_path)
    from voice_memo_archive.config import load_config

    archive_root = Path(load_config(config_path).archive_root)
    write_archive_entry(archive_root, ARCHIVE_METADATA, "Hello world.")

    state_path = tmp_path / "state.json"
    exit_code = main(["reconcile", "--config", str(config_path), "--state", str(state_path)])
    assert exit_code == 0
    from voice_memo_archive.state import load_state

    recordings = load_state(state_path).recordings
    assert recordings[ARCHIVE_METADATA["recording_id"]].status == RecordingStatus.PROCESSED


def test_verify_reports_clean_archive(capsys, tmp_path):
    config_path = _write_synthetic_config(tmp_path)
    exit_code = main(["verify", "--config", str(config_path)])
    assert exit_code == 0
    assert "entries=0 malformed=0 orphaned=0" in capsys.readouterr().out


def test_verify_reports_malformed_entries(capsys, tmp_path):
    config_path = _write_synthetic_config(tmp_path)
    from voice_memo_archive.config import load_config

    archive_root = Path(load_config(config_path).archive_root)
    bad_dir = archive_root / "2024" / "01" / "15"
    bad_dir.mkdir(parents=True)
    (bad_dir / "bad.md").write_text("not a valid archive file")

    exit_code = main(["verify", "--config", str(config_path)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "malformed" in err


def test_setup_with_yes_writes_config_and_plist_without_enabling(capsys, tmp_path, monkeypatch):
    # launchd.plist_path() is Path.home()-relative — must redirect it into
    # tmp_path or this would write a real file under the actual user's
    # ~/Library/LaunchAgents.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_path = tmp_path / "config.json"
    state_path = tmp_path / "state.json"
    recordings_source = tmp_path / "recordings"
    recordings_source.mkdir()

    exit_code = main(
        [
            "setup",
            "--config",
            str(config_path),
            "--state",
            str(state_path),
            "--recordings-source",
            str(recordings_source),
            "--archive-root",
            str(tmp_path / "archive"),
            "--yes",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert config_path.exists()
    assert (tmp_path / "Library/LaunchAgents" / f"{launchd.LABEL}.plist").exists()
    assert "Background automation not enabled" in out
    # Phase 7 exit criterion: users see what initial import will consider
    # before anything is written — must appear before the confirmation.
    assert "Initial import will consider 0 recording(s)." in out


def test_setup_declined_without_yes_writes_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    config_path = tmp_path / "config.json"
    recordings_source = tmp_path / "recordings"
    recordings_source.mkdir()

    exit_code = main(
        [
            "setup",
            "--config",
            str(config_path),
            "--state",
            str(tmp_path / "state.json"),
            "--recordings-source",
            str(recordings_source),
        ]
    )
    assert exit_code == 0
    assert not config_path.exists()
    assert "cancelled" in capsys.readouterr().out


def test_setup_enable_now_with_yes_calls_bootstrap_not_real_launchctl(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(launchd, "bootstrap", lambda path: calls.append(path))
    recordings_source = tmp_path / "recordings"
    recordings_source.mkdir()

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
            "--enable-now",
        ]
    )
    assert exit_code == 0
    assert len(calls) == 1
    assert "Background automation enabled" in capsys.readouterr().out


def test_parser_requires_a_command():
    parser = build_parser()
    try:
        parser.parse_args([])
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass
