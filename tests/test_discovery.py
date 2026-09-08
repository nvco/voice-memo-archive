import os
import plistlib
from pathlib import Path

import pytest

from voice_memo_archive import discovery
from voice_memo_archive.discovery import CandidateStatus, scan
from voice_memo_archive.state import RecordingState


def _make_recording(directory: Path, name: str, content: bytes = b"fake audio bytes") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def _make_sidecar(directory: Path, stem: str, uuid: str | None) -> None:
    sidecar_dir = directory / f"{stem}.composition"
    sidecar_dir.mkdir()
    manifest = {"RCComposedAVURL": f"file://{stem}.m4a"}
    if uuid is not None:
        manifest["RCSavedRecordingUUID"] = uuid
    with (sidecar_dir / "manifest.plist").open("wb") as manifest_file:
        plistlib.dump(manifest, manifest_file)


def test_scan_skips_excluded_entries(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")
    (tmp_path / "20240115 143022-ABC-track0.waveform").write_bytes(b"")
    (tmp_path / "Capture").mkdir()
    (tmp_path / "CaptureRecovery").mkdir()
    (tmp_path / ".CloudRecordings_SUPPORT").mkdir()
    (tmp_path / "CloudRecordings_ckAssets").mkdir()
    (tmp_path / "CloudRecordings.db").write_bytes(b"")
    (tmp_path / "CloudRecordings.db-shm").write_bytes(b"")
    (tmp_path / "CloudRecordings.db-wal").write_bytes(b"")
    _make_sidecar(tmp_path, "20240116 090000", "SOME-UUID")

    candidates = scan(tmp_path, {})

    assert [c.path.name for c in candidates] == ["20240115 143022-ABC.m4a"]


def test_scan_ignores_unsupported_extensions(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")
    _make_recording(tmp_path, "20240115 143022-ABC.txt")

    candidates = scan(tmp_path, {})

    assert [c.path.suffix for c in candidates] == [".m4a"]


def test_scan_classifies_new_recording(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.NEW
    assert candidate.recording_id == "ABC"
    assert candidate.source_format == "m4a"
    assert candidate.recorded_at_iso == "2024-01-15T14:30:22"


def test_scan_classifies_unchanged_when_fingerprint_matches(tmp_path: Path):
    path = _make_recording(tmp_path, "20240115 143022-ABC.m4a")
    info = path.stat()
    known = {
        "ABC": RecordingState(
            status="archived", source_size=info.st_size, source_mtime=info.st_mtime
        )
    }

    (candidate,) = scan(tmp_path, known)

    assert candidate.status is CandidateStatus.UNCHANGED


def test_scan_classifies_changed_when_fingerprint_differs(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")
    known = {"ABC": RecordingState(status="archived", source_size=1, source_mtime=1.0)}

    (candidate,) = scan(tmp_path, known)

    assert candidate.status is CandidateStatus.CHANGED


def test_scan_classifies_malformed_filename(tmp_path: Path):
    _make_recording(tmp_path, "not-a-recording-name.m4a")

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.MALFORMED_FILENAME
    assert candidate.recording_id is None


def test_scan_resolves_id_via_composition_sidecar(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022.m4a")
    _make_sidecar(tmp_path, "20240115 143022", "SIDECAR-UUID-1")

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.NEW
    assert candidate.recording_id == "SIDECAR-UUID-1"


def test_scan_unresolvable_id_when_no_sidecar(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022.m4a")

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.UNRESOLVABLE_ID
    assert candidate.recording_id is None


def test_scan_unresolvable_id_when_sidecar_missing_uuid_key(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022.m4a")
    _make_sidecar(tmp_path, "20240115 143022", uuid=None)

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.UNRESOLVABLE_ID


def test_scan_flags_duplicate_ids(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-DUP.m4a")
    _make_recording(tmp_path, "20240116 090000-DUP.qta")

    candidates = scan(tmp_path, {})

    assert {c.status for c in candidates} == {CandidateStatus.DUPLICATE_ID}
    assert len(candidates[0].detail["duplicate_of"]) == 1


def test_scan_does_not_flag_non_duplicate_ids(tmp_path: Path):
    _make_recording(tmp_path, "20240115 143022-A.m4a")
    _make_recording(tmp_path, "20240116 090000-B.m4a")

    candidates = scan(tmp_path, {})

    assert all(c.status is CandidateStatus.NEW for c in candidates)


def test_scan_marks_inaccessible_on_stat_error(tmp_path: Path, monkeypatch):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")

    def raise_permission_error(path, stability_check_delay):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(discovery, "_stat_with_stability_check", raise_permission_error)

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.INACCESSIBLE
    assert candidate.detail == {"errno": 13}


def test_scan_marks_unstable_when_stat_reads_disagree(tmp_path: Path, monkeypatch):
    _make_recording(tmp_path, "20240115 143022-ABC.m4a")

    monkeypatch.setattr(
        discovery, "_stat_with_stability_check", lambda path, stability_check_delay: None
    )

    (candidate,) = scan(tmp_path, {})

    assert candidate.status is CandidateStatus.UNSTABLE


def test_stat_with_stability_check_returns_fingerprint_for_stable_file(tmp_path: Path):
    path = _make_recording(tmp_path, "20240115 143022-ABC.m4a")
    result = discovery._stat_with_stability_check(path, stability_check_delay=0)
    expected = (path.stat().st_size, path.stat().st_mtime)
    assert result == expected


def test_scan_is_deterministically_ordered(tmp_path: Path):
    _make_recording(tmp_path, "20240116 090000-B.m4a")
    _make_recording(tmp_path, "20240115 143022-A.m4a")

    candidates = scan(tmp_path, {})

    assert [c.path.name for c in candidates] == [
        "20240115 143022-A.m4a",
        "20240116 090000-B.m4a",
    ]


def test_scan_never_writes_renames_or_deletes(tmp_path: Path, monkeypatch):
    _make_recording(tmp_path, "20240115 143022-A.m4a")
    _make_recording(tmp_path, "20240115 143022-A.txt")  # unsupported, ignored
    _make_recording(tmp_path, "20240116 090000.m4a")  # id-less, unresolvable
    _make_sidecar(tmp_path, "20240117 100000", "SOME-UUID")
    _make_recording(tmp_path, "20240117 100000.m4a")
    (tmp_path / "Capture").mkdir()
    (tmp_path / "CloudRecordings.db").write_bytes(b"")

    def _forbidden(*args, **kwargs):
        raise AssertionError("discovery must never write, rename, or delete")

    monkeypatch.setattr(os, "remove", _forbidden)
    monkeypatch.setattr(os, "unlink", _forbidden)
    monkeypatch.setattr(os, "rename", _forbidden)
    monkeypatch.setattr(os, "replace", _forbidden)
    monkeypatch.setattr(Path, "unlink", _forbidden)
    monkeypatch.setattr(Path, "rename", _forbidden)
    monkeypatch.setattr(Path, "write_bytes", _forbidden)
    monkeypatch.setattr(Path, "write_text", _forbidden)

    candidates = scan(tmp_path, {})

    assert len(candidates) == 3


def test_scan_raises_source_unreadable_when_folder_missing(tmp_path: Path):
    from voice_memo_archive.errors import ArchiveError

    with pytest.raises(ArchiveError):
        scan(tmp_path / "does-not-exist", {})
