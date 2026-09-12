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


def test_setup_fails_cleanly_when_recordings_source_does_not_exist(capsys, tmp_path, monkeypatch):
    # The candidate-count preview inside build_setup_plan reads the
    # recordings folder before anything is written; a missing/unreadable
    # source must fail cleanly (exit 1, a short message on stderr), not
    # crash with a raw traceback — matches how `scan` itself behaves.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_path = tmp_path / "config.json"

    exit_code = main(
        [
            "setup",
            "--config",
            str(config_path),
            "--state",
            str(tmp_path / "state.json"),
            "--recordings-source",
            str(tmp_path / "does-not-exist"),
            "--archive-root",
            str(tmp_path / "archive"),
            "--yes",
        ]
    )
    assert exit_code == 1
    assert "source_unreadable" in capsys.readouterr().err
    assert not config_path.exists()


def test_setup_interactive_menu_accepts_defaults_when_no_existing_config(
    capsys, tmp_path, monkeypatch
):
    # Import mode, schedule mode, and scan interval are left off entirely so
    # the menu must seed them from package defaults; pressing Enter at the
    # menu accepts every shown value unchanged. recordings-source/
    # archive-root are still given explicitly per this file's own convention
    # of never touching cli.py's real Application-Support/Voice-Memos
    # defaults.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    responses = iter(["", "y"])  # menu: continue with no edits; confirm: yes
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
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
            "--archive-root",
            str(tmp_path / "archive"),
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Current setup:" in out
    written = json.loads(config_path.read_text())
    assert written["import_mode"] == "all"
    assert written["schedule_mode"] == "monitoring"
    assert written["scan_interval_seconds"] == 900


def test_setup_interactive_menu_edits_a_setting_by_number(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Menu: an invalid selection, then edit import mode (3) — an invalid
    # choice there, then a valid one ("date"), which immediately asks for
    # the now-required import-since date; back at the menu, continue; then
    # confirm.
    responses = iter(["9", "3", "bogus", "date", "2026-01-01", "", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
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
            "--archive-root",
            str(tmp_path / "archive"),
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Please enter one of: 1, 2, 3, 4, 5, 6" in out  # the "9" selection
    assert "Please enter one of: all/date/new_only" in out  # the "bogus" mode
    written = json.loads(config_path.read_text())
    assert written["import_mode"] == "date"
    assert written["import_since"] == "2026-01-01"


def test_setup_interactive_menu_seeds_defaults_from_existing_config(capsys, tmp_path, monkeypatch):
    # Re-running setup to change one setting should mean "accept every
    # menu row's default except the one you want to change" — each default
    # must come from the *current* config.json, not the package's hardcoded
    # defaults. Per tasks/035-...md's "Also requested" note.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_path = tmp_path / "config.json"
    state_path = tmp_path / "state.json"
    recordings_source = tmp_path / "recordings"
    recordings_source.mkdir()
    archive_root = tmp_path / "archive"

    first_run = main(
        [
            "setup",
            "--config",
            str(config_path),
            "--state",
            str(state_path),
            "--recordings-source",
            str(recordings_source),
            "--archive-root",
            str(archive_root),
            "--schedule-mode",
            "scheduled",
            "--yes",
        ]
    )
    assert first_run == 0
    capsys.readouterr()

    # Second run: only scan-interval is given explicitly; everything else
    # must be seeded from what's already in config.json, and accepted as-is
    # by continuing past the menu with no edits.
    responses = iter(["", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    second_run = main(
        [
            "setup",
            "--config",
            str(config_path),
            "--state",
            str(state_path),
            "--recordings-source",
            str(recordings_source),
            "--scan-interval",
            "1800",
        ]
    )
    assert second_run == 0
    out = capsys.readouterr().out
    assert str(archive_root) in out  # shown in the menu, unchanged from before
    written = json.loads(config_path.read_text())
    assert written["archive_root"] == str(archive_root)
    assert written["schedule_mode"] == "scheduled"  # preserved, not reset to "monitoring"
    assert written["scan_interval_seconds"] == 1800


def test_setup_declined_without_yes_writes_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Every value-selecting flag is given explicitly, so the menu already
    # shows exactly what will be written; continue past it with no edits,
    # then decline the final "Proceed?" confirmation this test targets.
    responses = iter(["", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
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
            "--archive-root",
            str(tmp_path / "archive"),
            "--import-mode",
            "all",
            "--schedule-mode",
            "monitoring",
            "--scan-interval",
            "900",
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


def test_uninstall_removes_the_plist_and_never_touches_the_archive(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launchd, "bootout", lambda: None)  # never invoke real launchctl
    config_path = _write_synthetic_config(tmp_path)
    from voice_memo_archive.config import load_config

    archive_root = Path(load_config(config_path).archive_root)
    write_archive_entry(archive_root, ARCHIVE_METADATA, "Hello world.")
    plist_path = tmp_path / "Library/LaunchAgents" / f"{launchd.LABEL}.plist"
    plist_path.parent.mkdir(parents=True)
    plist_path.write_bytes(b"placeholder plist content")

    exit_code = main(
        ["uninstall", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )

    assert exit_code == 0
    assert not plist_path.exists()
    assert config_path.exists()  # not purged by default
    # The archive is completely untouched — this is a structural
    # guarantee (uninstall's code never reads archive_root at all), and
    # this assertion proves the file really does still exist on disk.
    entries = list(archive_root.rglob("*.md"))
    assert len(entries) == 1
    assert entries[0].read_text() != ""


def test_uninstall_with_no_plist_installed_reports_that_cleanly(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launchd, "bootout", lambda: None)
    config_path = _write_synthetic_config(tmp_path)
    exit_code = main(
        ["uninstall", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )
    assert exit_code == 0
    assert "No launchd job was installed" in capsys.readouterr().out


def test_uninstall_purge_config_removes_config_and_state(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launchd, "bootout", lambda: None)
    config_path = _write_synthetic_config(tmp_path)
    state_path = tmp_path / "state.json"
    save_state(state_path, State())

    exit_code = main(
        [
            "uninstall",
            "--config",
            str(config_path),
            "--state",
            str(state_path),
            "--purge-config",
        ]
    )
    assert exit_code == 0
    assert not config_path.exists()
    assert not state_path.exists()


def test_parser_requires_a_command():
    parser = build_parser()
    try:
        parser.parse_args([])
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass
