from datetime import datetime
from pathlib import Path

import mp4_builders as mp4
import pytest

from voice_memo_archive.config import load_config
from voice_memo_archive.setup import build_setup_plan, commit_setup, may_be_icloud_synced


def _write_recording(recordings_source: Path, filename: str, data: bytes) -> Path:
    recordings_source.mkdir(parents=True, exist_ok=True)
    path = recordings_source / filename
    path.write_bytes(data)
    return path


def test_may_be_icloud_synced_true_under_documents():
    assert may_be_icloud_synced(Path.home() / "Documents" / "Voice Memo Archive")


def test_may_be_icloud_synced_false_elsewhere(tmp_path: Path):
    assert may_be_icloud_synced(tmp_path / "archive") is False


def test_build_setup_plan_previews_all_mode_candidate_count(tmp_path: Path):
    recordings_source = tmp_path / "recordings"
    _write_recording(
        recordings_source,
        "20240115 143022-A.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    _write_recording(
        recordings_source,
        "20240116 090000-B.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    plan = build_setup_plan(recordings_source=str(recordings_source), import_mode="all")
    assert plan.candidate_preview_count == 2
    assert plan.setup_completed_at is None


def test_build_setup_plan_new_only_previews_zero(tmp_path: Path):
    recordings_source = tmp_path / "recordings"
    _write_recording(
        recordings_source,
        "20240115 143022-A.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    plan = build_setup_plan(recordings_source=str(recordings_source), import_mode="new_only")
    assert plan.candidate_preview_count == 0


def test_build_setup_plan_date_mode_previews_only_matching(tmp_path: Path):
    recordings_source = tmp_path / "recordings"
    _write_recording(
        recordings_source,
        "20240501 090000-OLD.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    _write_recording(
        recordings_source,
        "20240601 090000-NEW.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    plan = build_setup_plan(
        recordings_source=str(recordings_source), import_mode="date", import_since="2024-06-01"
    )
    assert plan.candidate_preview_count == 1


def test_build_setup_plan_date_mode_requires_import_since():
    # Validation raises before any recordings-folder scan would happen —
    # no recordings_source is passed on purpose, to prove this path never
    # reaches (and never needs) a real folder.
    with pytest.raises(ValueError):
        build_setup_plan(import_mode="date")


def test_build_setup_plan_rejects_unknown_import_mode():
    with pytest.raises(ValueError):
        build_setup_plan(import_mode="whenever")


def test_build_setup_plan_rejects_unknown_schedule_mode(tmp_path: Path):
    with pytest.raises(ValueError):
        build_setup_plan(recordings_source=str(tmp_path / "recordings"), schedule_mode="always")


def test_build_setup_plan_rejects_non_positive_interval(tmp_path: Path):
    with pytest.raises(ValueError):
        build_setup_plan(recordings_source=str(tmp_path / "recordings"), scan_interval_seconds=0)


def test_build_setup_plan_flags_documents_archive_root(tmp_path: Path):
    plan = build_setup_plan(
        recordings_source=str(tmp_path / "recordings"),
        import_mode="new_only",  # never scans, so no real recordings_source is needed either
        archive_root=str(Path.home() / "Documents" / "Voice Memo Archive"),
    )
    assert plan.archive_root_may_sync is True


def test_build_setup_plan_does_not_write_config(tmp_path: Path):
    config_path = tmp_path / "config.json"
    build_setup_plan(recordings_source=str(tmp_path / "recordings"), import_mode="new_only")
    assert not config_path.exists()


def test_commit_setup_writes_config_and_sets_completed_at(tmp_path: Path):
    recordings_source = tmp_path / "recordings"
    archive_root = tmp_path / "archive"
    config_path = tmp_path / "config.json"
    plan = build_setup_plan(
        recordings_source=str(recordings_source),
        archive_root=str(archive_root),
        import_mode="new_only",
        schedule_mode="scheduled",
        scan_interval_seconds=1800,
    )
    committed = commit_setup(config_path, plan, now=lambda: datetime(2024, 1, 15, 12, 0))

    assert committed.setup_completed_at is not None
    saved = load_config(config_path)
    assert saved.recordings_source == str(recordings_source)
    assert saved.archive_root == str(archive_root)
    assert saved.import_mode == "new_only"
    assert saved.schedule_mode == "scheduled"
    assert saved.scan_interval_seconds == 1800
    assert saved.setup_completed_at == committed.setup_completed_at


def test_commit_setup_is_idempotent_on_rerun(tmp_path: Path):
    config_path = tmp_path / "config.json"
    (tmp_path / "recordings").mkdir()
    recordings_source = str(tmp_path / "recordings")
    plan_a = build_setup_plan(recordings_source=recordings_source, import_mode="all")
    commit_setup(config_path, plan_a, now=lambda: datetime(2024, 1, 15, 12, 0))

    plan_b = build_setup_plan(
        recordings_source=recordings_source, import_mode="date", import_since="2024-06-01"
    )
    commit_setup(config_path, plan_b, now=lambda: datetime(2024, 1, 16, 12, 0))

    saved = load_config(config_path)
    assert saved.import_mode == "date"
    assert saved.import_since == "2024-06-01"
