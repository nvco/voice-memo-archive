import hashlib
from pathlib import Path

import pytest

from voice_memo_archive.archive import (
    inspect_archive,
    read_archive_entry,
    rebuild_state_from_archive,
    write_archive_entry,
)
from voice_memo_archive.errors import ArchiveError, ErrorCategory
from voice_memo_archive.state import RecordingStatus

BASE_METADATA = {
    "recording_id": "ABCDEF12-3456-7890-ABCD-EF1234567890",
    "source_filename": "20240115 143022-ABCDEF12-3456-7890-ABCD-EF1234567890.m4a",
    "source_format": "m4a",
    "source_size": 123456,
    "source_mtime": 1705329022.0,
    "recorded_at": "2024-01-15T14:30:22-08:00",
    "locale": "en_US",
    "extraction_format_version": 1,
    "archived_at": "2024-01-15T20:00:00Z",
}


def _transcript_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_write_creates_expected_year_month_day_path(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    expected = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    assert expected.exists()


def test_write_then_read_round_trips_metadata_and_body(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    metadata, body = read_archive_entry(path)
    assert body == "Hello world."
    assert metadata["recording_id"] == BASE_METADATA["recording_id"]
    assert metadata["transcript_sha256"] == _transcript_sha256("Hello world.")


def test_write_computes_transcript_hash_from_actual_text_not_caller_input(tmp_path: Path):
    metadata_with_bogus_hash = dict(BASE_METADATA, transcript_sha256="not-a-real-hash")
    # transcript_sha256 isn't in yaml_meta.REQUIRED_FIELDS's caller contract at all —
    # write_archive_entry must compute its own regardless of what sneaks into the dict.
    write_archive_entry(tmp_path, metadata_with_bogus_hash, "Real text.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    metadata, _body = read_archive_entry(path)
    assert metadata["transcript_sha256"] == _transcript_sha256("Real text.")


@pytest.mark.parametrize(
    "transcript_text",
    [
        "line one\n---\nline two still in the body",
        "---",
        "Unicode: café 日本語 🎙️",
        "trailing colon: like this",
        "",
    ],
)
def test_yaml_markdown_boundary_cases_round_trip(tmp_path: Path, transcript_text: str):
    write_archive_entry(tmp_path, BASE_METADATA, transcript_text)
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    _metadata, body = read_archive_entry(path)
    assert body == transcript_text


def test_identical_rewrite_is_a_silent_no_op(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    original_mtime = path.stat().st_mtime_ns
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    assert path.stat().st_mtime_ns == original_mtime


def test_different_source_filename_raises_duplicate_conflict_and_preserves_original(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    conflicting = dict(BASE_METADATA, source_filename="a different filename.m4a")
    with pytest.raises(ArchiveError) as excinfo:
        write_archive_entry(tmp_path, conflicting, "Hello world.")
    assert excinfo.value.category == ErrorCategory.ARCHIVE_CONFLICT
    assert "duplicate" in excinfo.value.message
    _metadata, body = read_archive_entry(path)
    assert body == "Hello world."


def test_changed_source_fingerprint_raises_conflict_and_preserves_original(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    changed = dict(BASE_METADATA, source_size=999999)
    with pytest.raises(ArchiveError) as excinfo:
        write_archive_entry(tmp_path, changed, "Hello world.")
    assert excinfo.value.category == ErrorCategory.ARCHIVE_CONFLICT
    assert "changed source" in excinfo.value.message
    _metadata, body = read_archive_entry(path)
    assert body == "Hello world."


def test_changed_transcript_with_same_fingerprint_raises_conflict_and_preserves_original(
    tmp_path: Path,
):
    write_archive_entry(tmp_path, BASE_METADATA, "Original transcript.")
    path = tmp_path / "2024" / "01" / "15" / f"143022-{BASE_METADATA['recording_id']}.md"
    with pytest.raises(ArchiveError) as excinfo:
        write_archive_entry(tmp_path, BASE_METADATA, "Different transcript text.")
    assert excinfo.value.category == ErrorCategory.ARCHIVE_CONFLICT
    assert "changed transcript" in excinfo.value.message
    _metadata, body = read_archive_entry(path)
    assert body == "Original transcript."


def test_write_never_leaves_a_temp_file_behind(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    day_dir = tmp_path / "2024" / "01" / "15"
    files = list(day_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".md"


def test_unsafe_recording_id_is_rejected(tmp_path: Path):
    unsafe = dict(BASE_METADATA, recording_id="../escape")
    with pytest.raises(ValueError):
        write_archive_entry(tmp_path, unsafe, "text")


def test_inspect_archive_on_missing_root_returns_empty(tmp_path: Path):
    inspection = inspect_archive(tmp_path / "does-not-exist")
    assert inspection.entries == ()
    assert inspection.malformed == ()
    assert inspection.orphaned == ()


def test_inspect_archive_finds_valid_entries(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    inspection = inspect_archive(tmp_path)
    assert len(inspection.entries) == 1
    assert inspection.entries[0].metadata["recording_id"] == BASE_METADATA["recording_id"]
    assert inspection.malformed == ()
    assert inspection.orphaned == ()


def test_inspect_archive_flags_malformed_frontmatter(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    bad_path = tmp_path / "2024" / "01" / "15" / "bad.md"
    bad_path.write_text("not a valid archive file at all", encoding="utf-8")
    inspection = inspect_archive(tmp_path)
    assert len(inspection.entries) == 1
    assert len(inspection.malformed) == 1
    assert inspection.malformed[0].path == bad_path


def test_inspect_archive_flags_incomplete_frontmatter_as_malformed(tmp_path: Path):
    incomplete_path = tmp_path / "2024" / "01" / "15"
    incomplete_path.mkdir(parents=True)
    (incomplete_path / "incomplete.md").write_text(
        "---\nrecording_id: only-one-field\n---\n\nbody text",
        encoding="utf-8",
    )
    inspection = inspect_archive(tmp_path)
    assert inspection.entries == ()
    assert len(inspection.malformed) == 1


def test_inspect_archive_flags_non_markdown_files_as_orphaned(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    stray = tmp_path / "2024" / "01" / "15" / ".143022-stray.md.abc123.tmp"
    stray.write_text("leftover from a killed process", encoding="utf-8")
    inspection = inspect_archive(tmp_path)
    assert len(inspection.entries) == 1
    assert inspection.orphaned == (stray,)


def test_rebuild_state_from_archive_reconstructs_fingerprint(tmp_path: Path):
    write_archive_entry(tmp_path, BASE_METADATA, "Hello world.")
    rebuilt = rebuild_state_from_archive(tmp_path)
    state = rebuilt[BASE_METADATA["recording_id"]]
    assert state.status == RecordingStatus.PROCESSED
    assert state.source_filename == BASE_METADATA["source_filename"]
    assert state.source_size == BASE_METADATA["source_size"]
    assert state.source_mtime == BASE_METADATA["source_mtime"]
    assert state.first_seen_at is None
