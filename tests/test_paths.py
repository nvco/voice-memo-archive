from datetime import datetime
from pathlib import Path

from voice_memo_archive.paths import (
    archive_date_parts,
    attach_local_timezone,
    parse_recording_filename,
    redact_home_path,
)


def test_parse_filename_with_id():
    info = parse_recording_filename("20240115 143022-ABCDE12345.m4a")
    assert info is not None
    assert info.recorded_at == datetime(2024, 1, 15, 14, 30, 22)
    assert info.id_suffix == "ABCDE12345"
    assert info.extension == "m4a"


def test_parse_filename_without_id():
    info = parse_recording_filename("20240115 143022.m4a")
    assert info is not None
    assert info.id_suffix is None


def test_parse_filename_qta():
    info = parse_recording_filename("20240115 143022-XYZ.qta")
    assert info is not None
    assert info.extension == "qta"


def test_parse_filename_unsupported_extension_returns_none():
    assert parse_recording_filename("20240115 143022-ABC.waveform") is None


def test_parse_filename_non_matching_returns_none():
    assert parse_recording_filename("not-a-recording.txt") is None
    assert parse_recording_filename("CloudRecordings.db") is None


def test_archive_date_parts_zero_padded():
    assert archive_date_parts(datetime(2024, 3, 5, 9, 0, 0)) == ("2024", "03", "05")


def test_attach_local_timezone_preserves_wall_clock():
    naive = datetime(2024, 3, 5, 9, 0, 0)
    aware = attach_local_timezone(naive)
    assert aware.tzinfo is not None
    assert (aware.hour, aware.minute, aware.second) == (9, 0, 0)


def test_attach_local_timezone_rejects_aware_input():
    aware = attach_local_timezone(datetime(2024, 3, 5, 9, 0, 0))
    try:
        attach_local_timezone(aware)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_redact_home_path():
    home = Path.home()
    expected = "~/Documents/Voice Memo Archive"
    assert redact_home_path(home / "Documents" / "Voice Memo Archive") == expected
    assert redact_home_path(home) == "~"
    assert redact_home_path("/var/tmp/unrelated") == "/var/tmp/unrelated"
