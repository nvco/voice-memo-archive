import json
from pathlib import Path

import pytest

from voice_memo_archive.errors import StateError
from voice_memo_archive.state import RecordingState, State, load_state, save_state


def test_load_state_missing_file_returns_empty_state(tmp_path: Path):
    state = load_state(tmp_path / "state.json")
    assert state == State()
    assert state.recordings == {}


def test_save_then_load_round_trip_with_recordings(tmp_path: Path):
    path = tmp_path / "state.json"
    original = State(
        recordings={
            "REC-1": RecordingState(status="archived", last_scanned_at="2024-01-15T14:30:22Z"),
            "REC-2": RecordingState(
                status="failed", retry_count=2, last_error_category="transcript_malformed"
            ),
        },
        last_scan_started_at="2024-01-15T14:00:00Z",
        last_scan_completed_at="2024-01-15T14:05:00Z",
    )
    save_state(path, original)
    loaded = load_state(path)
    assert loaded == original


def test_load_state_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not json")
    with pytest.raises(StateError):
        load_state(path)


def test_load_state_rejects_recording_missing_status(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings": {"REC-1": {"retry_count": 0}},
            }
        )
    )
    with pytest.raises(StateError):
        load_state(path)


def test_state_survives_reset_by_returning_defaults(tmp_path: Path):
    # Simulates a wiped/rebuilt state.json: settings/behavior must not
    # depend on any prior state having existed.
    path = tmp_path / "state.json"
    path.unlink(missing_ok=True)
    state = load_state(path)
    assert state.recordings == {}
    assert state.last_scan_started_at is None
