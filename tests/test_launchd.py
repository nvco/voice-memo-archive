import plistlib
import subprocess
from pathlib import Path

from voice_memo_archive import launchd


def test_build_plist_monitoring_mode_includes_watch_paths(tmp_path: Path):
    plist = launchd.build_plist(
        config_path=tmp_path / "config.json",
        state_path=tmp_path / "state.json",
        scan_interval_seconds=900,
        watch_recordings_path=tmp_path / "recordings",
        log_path=tmp_path / "scan.log",
        python_executable="/usr/bin/python3",
    )
    assert plist["Label"] == launchd.LABEL
    assert plist["StartInterval"] == 900
    assert plist["RunAtLoad"] is True
    assert plist["WatchPaths"] == [str(tmp_path / "recordings")]
    assert plist["ProgramArguments"] == [
        "/usr/bin/python3",
        "-m",
        "voice_memo_archive.cli",
        "scan",
        "--config",
        str(tmp_path / "config.json"),
        "--state",
        str(tmp_path / "state.json"),
    ]


def test_build_plist_scheduled_mode_omits_watch_paths(tmp_path: Path):
    plist = launchd.build_plist(
        config_path=tmp_path / "config.json",
        state_path=tmp_path / "state.json",
        scan_interval_seconds=1800,
        watch_recordings_path=None,
        log_path=tmp_path / "scan.log",
    )
    assert "WatchPaths" not in plist


def test_write_plist_is_valid_and_idempotent(tmp_path: Path):
    path = tmp_path / "test.plist"
    plist = {"Label": launchd.LABEL, "StartInterval": 900}
    launchd.write_plist(path, plist)
    first_bytes = path.read_bytes()
    launchd.write_plist(path, plist)
    assert path.read_bytes() == first_bytes
    assert plistlib.loads(first_bytes) == plist


def test_install_writes_a_valid_plist_at_the_expected_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    written = launchd.install(
        config_path=tmp_path / "config.json",
        state_path=tmp_path / "state.json",
        recordings_source=tmp_path / "recordings",
        schedule_mode="monitoring",
        scan_interval_seconds=900,
    )
    assert written == tmp_path / "Library/LaunchAgents" / f"{launchd.LABEL}.plist"
    loaded = plistlib.loads(written.read_bytes())
    assert loaded["WatchPaths"] == [str(tmp_path / "recordings")]


def test_install_scheduled_mode_produces_no_watch_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    written = launchd.install(
        config_path=tmp_path / "config.json",
        state_path=tmp_path / "state.json",
        recordings_source=tmp_path / "recordings",
        schedule_mode="scheduled",
        scan_interval_seconds=900,
    )
    loaded = plistlib.loads(written.read_bytes())
    assert "WatchPaths" not in loaded


def test_bootstrap_invokes_launchctl_with_expected_args(monkeypatch):
    calls = []
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kwargs: calls.append((argv, kwargs)) or None
    )
    launchd.bootstrap(Path("/some/path.plist"))
    (argv, kwargs) = calls[0]
    assert argv[0] == "launchctl"
    assert argv[1] == "bootstrap"
    assert argv[-1] == "/some/path.plist"
    assert kwargs.get("check") is True


def test_bootout_invokes_launchctl_with_check_false(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        # A real launchctl bootout on an unloaded job exits nonzero; with
        # check=False that must not raise — this stands in for that case.
        return subprocess.CompletedProcess(argv, returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    launchd.bootout()  # must not raise
    (argv, kwargs) = calls[0]
    assert argv[:2] == ["launchctl", "bootout"]
    assert kwargs.get("check") is False


def test_is_loaded_true_on_zero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, returncode=0),
    )
    assert launchd.is_loaded() is True


def test_is_loaded_false_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, returncode=1),
    )
    assert launchd.is_loaded() is False


def test_is_loaded_none_when_launchctl_is_unavailable(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("launchctl not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert launchd.is_loaded() is None
