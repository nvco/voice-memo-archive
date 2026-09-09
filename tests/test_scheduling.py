import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import mp4_builders as mp4

from voice_memo_archive import archive, scheduling
from voice_memo_archive.errors import ErrorCategory
from voice_memo_archive.paths import format_utc_iso
from voice_memo_archive.state import RecordingState, RecordingStatus, State, load_state

RECORDING_ID = "AAAAAAAA-1111-2222-3333-444444444444"


def _write_config(tmp_path: Path, **extra) -> tuple[Path, Path, Path]:
    recordings_source = tmp_path / "recordings"
    archive_root = tmp_path / "archive"
    recordings_source.mkdir(exist_ok=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": str(recordings_source),
                "archive_root": str(archive_root),
                **extra,
            }
        )
    )
    return config_path, recordings_source, archive_root


def _write_recording(recordings_source: Path, filename: str, data: bytes) -> Path:
    path = recordings_source / filename
    path.write_bytes(data)
    return path


def _clock(dt: datetime):
    return lambda: dt


def test_new_ok_recording_is_processed_and_archived(tmp_path: Path):
    config_path, recordings_source, archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    assert summary.result_counts == {"processed": 1}
    assert summary.unidentified == ()
    state = load_state(state_path)
    record = state.recordings[RECORDING_ID]
    assert record.status == RecordingStatus.PROCESSED
    assert record.first_seen_at is not None
    inspection = archive.inspect_archive(archive_root)
    assert len(inspection.entries) == 1
    assert inspection.entries[0].metadata["recording_id"] == RECORDING_ID


def test_unchanged_processed_recording_is_never_reextracted(tmp_path: Path, monkeypatch):
    config_path, recordings_source, archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"
    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    call_count = 0
    from voice_memo_archive import extraction

    original = extraction.extract_transcript

    def spy(path):
        nonlocal call_count
        call_count += 1
        return original(path)

    monkeypatch.setattr(scheduling.extraction, "extract_transcript", spy)

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 16, 0)))

    assert call_count == 0
    assert summary.result_counts == {"processed": 1}


def test_force_rescans_a_stable_processed_recording(tmp_path: Path, monkeypatch):
    config_path, recordings_source, archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"
    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    call_count = 0
    from voice_memo_archive import extraction

    original = extraction.extract_transcript

    def spy(path):
        nonlocal call_count
        call_count += 1
        return original(path)

    monkeypatch.setattr(scheduling.extraction, "extract_transcript", spy)

    summary = scheduling.run_scan(
        config_path, state_path, now=_clock(datetime(2024, 1, 15, 16, 0)), force=True
    )

    assert call_count == 1
    assert summary.result_counts == {"processed": 1}


def test_empty_transcript_requires_two_scans_to_confirm_skipped_empty(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_empty_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))
    first = load_state(state_path).recordings[RECORDING_ID]
    assert first.status == RecordingStatus.PENDING

    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 16, 0)))
    second = load_state(state_path).recordings[RECORDING_ID]
    assert second.status == RecordingStatus.SKIPPED_EMPTY


def test_malformed_filename_is_reported_but_never_persisted(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    _write_recording(recordings_source, "not-a-valid-filename.m4a", b"irrelevant")
    state_path = tmp_path / "state.json"

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    assert len(summary.unidentified) == 1
    assert summary.unidentified[0].status == "malformed_filename"
    state = load_state(state_path)
    assert state.recordings == {}


def test_unresolvable_id_is_reported_but_never_persisted(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    # No "-<ID>" suffix and no composition sidecar to resolve it from.
    _write_recording(recordings_source, "20240115 143022.m4a", b"irrelevant")
    state_path = tmp_path / "state.json"

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    assert len(summary.unidentified) == 1
    assert summary.unidentified[0].status == "unresolvable_id"
    assert load_state(state_path).recordings == {}


def test_duplicate_id_becomes_conflict(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    _write_recording(
        recordings_source,
        f"20240116 090000-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 16, 10, 0)))

    record = load_state(state_path).recordings[RECORDING_ID]
    assert record.status == RecordingStatus.CONFLICT
    assert record.last_error_category == ErrorCategory.ARCHIVE_CONFLICT.value


def test_transient_failure_retries_with_backoff_then_needs_attention(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    # No moov box at all -> extraction.ExtractionStatus.MALFORMED every time.
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.ftyp_box() + mp4.mdat_box(b"\x00" * 16),
    )
    state_path = tmp_path / "state.json"
    t = datetime(2024, 1, 15, 15, 0, tzinfo=UTC)

    scheduling.run_scan(config_path, state_path, now=_clock(t))
    record = load_state(state_path).recordings[RECORDING_ID]
    assert record.status == RecordingStatus.FAILED
    assert record.retry_count == 1
    assert record.last_error_category == ErrorCategory.TRANSCRIPT_MALFORMED.value

    # Too soon: still within the first retry delay, so nothing changes.
    t_too_soon = t + timedelta(seconds=1)
    scheduling.run_scan(config_path, state_path, now=_clock(t_too_soon))
    assert load_state(state_path).recordings[RECORDING_ID].retry_count == 1

    # Advance past each successive retry delay to exhaust all three.
    for expected_attempt in (2, 3):
        t += scheduling.RETRY_DELAYS[expected_attempt - 2] + timedelta(seconds=1)
        scheduling.run_scan(config_path, state_path, now=_clock(t))
        record = load_state(state_path).recordings[RECORDING_ID]
        assert record.status == RecordingStatus.FAILED
        assert record.retry_count == expected_attempt

    t += scheduling.RETRY_DELAYS[-1] + timedelta(seconds=1)
    scheduling.run_scan(config_path, state_path, now=_clock(t))
    record = load_state(state_path).recordings[RECORDING_ID]
    assert record.status == RecordingStatus.NEEDS_ATTENTION
    assert record.next_retry_at is None


def test_source_change_reopens_needs_attention(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path)
    path = _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.ftyp_box() + mp4.mdat_box(b"\x00" * 16),
    )
    state_path = tmp_path / "state.json"
    t = datetime(2024, 1, 15, 15, 0, tzinfo=UTC)
    for _ in range(4):
        scheduling.run_scan(config_path, state_path, now=_clock(t))
        t += timedelta(hours=3)
    assert load_state(state_path).recordings[RECORDING_ID].status == RecordingStatus.NEEDS_ATTENTION

    # Fix the source file (now a genuinely valid container) — this is a
    # source-file change, which reopens processing immediately.
    path.write_bytes(mp4.build_m4a_container(mp4.make_transcript_json()))
    scheduling.run_scan(config_path, state_path, now=_clock(t))
    record = load_state(state_path).recordings[RECORDING_ID]
    assert record.status == RecordingStatus.PROCESSED
    assert record.retry_count == 0


def test_import_mode_new_only_excludes_a_preexisting_recording(tmp_path: Path):
    # Recorded 5 local calendar days before setup completes — unambiguous
    # regardless of the test machine's timezone.
    setup_completed_at = format_utc_iso(datetime(2024, 1, 16, 12, 0).astimezone())
    config_path, recordings_source, _archive_root = _write_config(
        tmp_path, import_mode="new_only", setup_completed_at=setup_completed_at
    )
    _write_recording(
        recordings_source,
        f"20240110 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 17, 9, 0)))

    assert summary.result_counts == {}
    assert load_state(state_path).recordings == {}


def test_import_mode_new_only_includes_a_recording_from_the_cutoff_day(tmp_path: Path):
    # Both anchored to local noon on the same local calendar day, so this
    # is unambiguous regardless of the test machine's timezone —
    # day-granularity means a recording made earlier that same day still
    # counts as "new".
    setup_completed_at = format_utc_iso(datetime(2024, 1, 16, 12, 0).astimezone())
    config_path, recordings_source, _archive_root = _write_config(
        tmp_path, import_mode="new_only", setup_completed_at=setup_completed_at
    )
    _write_recording(
        recordings_source,
        f"20240116 080000-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    summary = scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 17, 9, 0)))

    assert summary.result_counts == {"processed": 1}


def test_import_mode_date_filters_by_recorded_at(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(
        tmp_path, import_mode="date", import_since="2024-06-01"
    )
    older_id = "OLDER-1111-2222-3333-444444444444"
    newer_id = "NEWER-1111-2222-3333-444444444444"
    _write_recording(
        recordings_source,
        f"20240501 090000-{older_id}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    _write_recording(
        recordings_source,
        f"20240601 090000-{newer_id}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"

    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 6, 2, 9, 0)))

    recordings = load_state(state_path).recordings
    assert older_id not in recordings
    assert recordings[newer_id].status == RecordingStatus.PROCESSED


def test_import_cutoff_never_retroactively_excludes_an_already_tracked_recording(tmp_path: Path):
    config_path, recordings_source, _archive_root = _write_config(tmp_path, import_mode="all")
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.ftyp_box() + mp4.mdat_box(b"\x00" * 16),  # MALFORMED -> tracked as failed
    )
    state_path = tmp_path / "state.json"
    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))
    assert RECORDING_ID in load_state(state_path).recordings

    # Switch to "date" mode with a cutoff well after this recording — it's
    # already tracked, so it must keep being retried, not silently frozen.
    config_path, _rs, _ar = _write_config(tmp_path, import_mode="date", import_since="2030-01-01")
    scheduling.run_scan(
        config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 6))
    )  # past the first retry delay
    assert load_state(state_path).recordings[RECORDING_ID].retry_count == 2


def test_acknowledge_suppresses_but_preserves_facts():
    state = State(
        recordings={
            RECORDING_ID: RecordingState(
                status=RecordingStatus.NEEDS_ATTENTION,
                retry_count=3,
                last_error_category="transcript_malformed",
            )
        }
    )
    updated = scheduling.acknowledge(state, RECORDING_ID)
    record = updated.recordings[RECORDING_ID]
    assert record.status == RecordingStatus.ACKNOWLEDGED
    assert record.retry_count == 3
    assert record.last_error_category == "transcript_malformed"


def test_acknowledge_rejects_non_needs_attention_record():
    state = State(recordings={RECORDING_ID: RecordingState(status=RecordingStatus.PROCESSED)})
    try:
        scheduling.acknowledge(state, RECORDING_ID)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_retry_resets_a_needs_attention_record():
    state = State(
        recordings={
            RECORDING_ID: RecordingState(
                status=RecordingStatus.NEEDS_ATTENTION,
                retry_count=3,
                next_retry_at="2024-01-15T00:00:00Z",
            )
        }
    )
    updated = scheduling.retry(state, RECORDING_ID)
    record = updated.recordings[RECORDING_ID]
    assert record.status == RecordingStatus.PENDING
    assert record.retry_count == 0
    assert record.next_retry_at is None


def test_retry_rejects_processed_record():
    state = State(recordings={RECORDING_ID: RecordingState(status=RecordingStatus.PROCESSED)})
    try:
        scheduling.retry(state, RECORDING_ID)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_retry_all_needing_attention_only_touches_matching_records():
    state = State(
        recordings={
            "A": RecordingState(status=RecordingStatus.NEEDS_ATTENTION),
            "B": RecordingState(status=RecordingStatus.PROCESSED),
            "C": RecordingState(status=RecordingStatus.NEEDS_ATTENTION),
        }
    )
    updated = scheduling.retry_all_needing_attention(state)
    assert updated.recordings["A"].status == RecordingStatus.PENDING
    assert updated.recordings["B"].status == RecordingStatus.PROCESSED
    assert updated.recordings["C"].status == RecordingStatus.PENDING


def test_reconcile_with_archive_rebuilds_processed_and_preserves_the_rest(tmp_path: Path):
    archive_root = tmp_path / "archive"
    metadata = {
        "recording_id": RECORDING_ID,
        "source_filename": f"20240115 143022-{RECORDING_ID}.m4a",
        "source_format": "m4a",
        "source_size": 100,
        "source_mtime": 123.0,
        "recorded_at": "2024-01-15T14:30:22-08:00",
        "locale": "en_US",
        "extraction_format_version": 1,
        "archived_at": "2024-01-15T20:00:00Z",
    }
    archive.write_archive_entry(archive_root, metadata, "Hello world.")

    starting_state = State(
        recordings={
            "UNRELATED-FAILED": RecordingState(status=RecordingStatus.FAILED, retry_count=2)
        }
    )
    reconciled = scheduling.reconcile_with_archive(starting_state, archive_root)

    assert reconciled.recordings[RECORDING_ID].status == RecordingStatus.PROCESSED
    assert reconciled.recordings[RECORDING_ID].source_size == 100
    assert reconciled.recordings["UNRELATED-FAILED"].status == RecordingStatus.FAILED
    assert reconciled.recordings["UNRELATED-FAILED"].retry_count == 2


def test_run_scan_recovers_from_corrupt_state_json(tmp_path: Path):
    config_path, recordings_source, archive_root = _write_config(tmp_path)
    _write_recording(
        recordings_source,
        f"20240115 143022-{RECORDING_ID}.m4a",
        mp4.build_m4a_container(mp4.make_transcript_json()),
    )
    state_path = tmp_path / "state.json"
    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 15, 0)))

    state_path.write_text("this is not valid json at all")

    # Must not crash, and must recover the already-completed archive entry
    # rather than treating it as brand new.
    scheduling.run_scan(config_path, state_path, now=_clock(datetime(2024, 1, 15, 16, 0)))
    record = load_state(state_path).recordings[RECORDING_ID]
    assert record.status == RecordingStatus.PROCESSED
    assert len(archive.inspect_archive(archive_root).entries) == 1
