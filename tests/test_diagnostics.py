import errno
from pathlib import Path

from voice_memo_archive import diagnostics, launchd
from voice_memo_archive.config import Config, save_config
from voice_memo_archive.state import RecordingState, RecordingStatus, State, save_state


def test_check_recordings_access_ok(tmp_path: Path):
    (tmp_path / "recordings").mkdir()
    result = diagnostics.check_recordings_access(tmp_path / "recordings")
    assert result.ok is True


def test_check_recordings_access_not_found(tmp_path: Path):
    result = diagnostics.check_recordings_access(tmp_path / "does-not-exist")
    assert result.ok is False
    assert "not found" in result.detail


def test_check_recordings_access_detects_full_disk_access_denial(tmp_path: Path, monkeypatch):
    target = tmp_path / "recordings"
    target.mkdir()

    def raising_iterdir(self):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(Path, "iterdir", raising_iterdir)
    result = diagnostics.check_recordings_access(target)
    assert result.ok is False
    assert "Full Disk Access" in result.detail


def test_check_recordings_access_generic_permission_error(tmp_path: Path, monkeypatch):
    target = tmp_path / "recordings"
    target.mkdir()

    def raising_iterdir(self):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "iterdir", raising_iterdir)
    result = diagnostics.check_recordings_access(target)
    assert result.ok is False
    assert "Full Disk Access" not in result.detail


def test_check_archive_root_writable_true_for_existing_writable_dir(tmp_path: Path):
    result = diagnostics.check_archive_root_writable(tmp_path)
    assert result.ok is True


def test_check_archive_root_writable_walks_up_to_existing_ancestor_without_creating_anything(
    tmp_path: Path,
):
    result = diagnostics.check_archive_root_writable(tmp_path / "not" / "yet" / "created")
    assert result.ok is True
    assert not (tmp_path / "not").exists()


def test_check_config_valid(tmp_path: Path):
    path = tmp_path / "config.json"
    save_config(path, Config())
    assert diagnostics.check_config(path).ok is True


def test_check_config_invalid(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("not json")
    assert diagnostics.check_config(path).ok is False


def test_check_state_valid(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(path, State())
    assert diagnostics.check_state(path).ok is True


def test_check_state_invalid_is_reported_as_self_healing(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not json")
    result = diagnostics.check_state(path)
    assert result.ok is False
    assert "self-heal" in result.detail


def test_check_scheduler_reports_loaded(monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda: True)
    assert diagnostics.check_scheduler().ok is True


def test_check_scheduler_reports_not_loaded(monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda: False)
    assert diagnostics.check_scheduler().ok is False


def test_check_scheduler_reports_unknown_as_ok(monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda: None)
    result = diagnostics.check_scheduler()
    assert result.ok is True
    assert "unknown" in result.detail


def test_check_pending_work_flags_needs_attention_and_conflict(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(
        path,
        State(
            recordings={
                "A": RecordingState(status=RecordingStatus.PROCESSED),
                "B": RecordingState(status=RecordingStatus.NEEDS_ATTENTION),
            }
        ),
    )
    result = diagnostics.check_pending_work(path)
    assert result.ok is False
    assert "needs_attention=1" in result.detail


def test_check_pending_work_ok_when_nothing_needs_attention(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(path, State(recordings={"A": RecordingState(status=RecordingStatus.PROCESSED)}))
    assert diagnostics.check_pending_work(path).ok is True


def test_run_doctor_aggregates_every_check(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launchd, "is_loaded", lambda: None)
    config_path = tmp_path / "config.json"
    state_path = tmp_path / "state.json"
    recordings_source = tmp_path / "recordings"
    archive_root = tmp_path / "archive"
    recordings_source.mkdir()
    save_config(
        config_path,
        Config(recordings_source=str(recordings_source), archive_root=str(archive_root)),
    )
    results = diagnostics.run_doctor(config_path=config_path, state_path=state_path)
    names = [r.name for r in results]
    assert names == [
        "config",
        "recordings_source",
        "archive_root",
        "state",
        "scheduler",
        "pending_work",
    ]
    assert all(r.ok for r in results)


def test_run_doctor_skips_rather_than_guesses_when_config_is_invalid(tmp_path: Path, monkeypatch):
    # A corrupt config.json might be hiding a customized recordings_source
    # — falling back to the real global default and scanning *that* would
    # be both wrong and, on a real machine, a genuine privacy hazard. Must
    # skip, not silently substitute the default.
    monkeypatch.setattr(launchd, "is_loaded", lambda: None)
    config_path = tmp_path / "config.json"
    config_path.write_text("not json")

    results = diagnostics.run_doctor(config_path=config_path, state_path=tmp_path / "state.json")
    by_name = {r.name: r for r in results}
    assert by_name["config"].ok is False
    assert by_name["recordings_source"].ok is True
    assert "skipped" in by_name["recordings_source"].detail
    assert by_name["archive_root"].ok is True
    assert "skipped" in by_name["archive_root"].detail
