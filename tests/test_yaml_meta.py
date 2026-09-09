import pytest

from voice_memo_archive.yaml_meta import dump_metadata, load_metadata

VALID_FIELDS = {
    "recording_id": "sample transcript text ID",
    "source_filename": "20240115 143022-sample transcript text ID.m4a",
    "source_format": "m4a",
    "source_size": 123456,
    "source_mtime": 1705329022.0,
    "recorded_at": "2024-01-15T14:30:22-08:00",
    "locale": "en_US",
    "extraction_format_version": 1,
    "transcript_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85",
    "archived_at": "2024-01-15T20:00:00Z",
}


def test_dump_then_load_round_trip():
    text = dump_metadata(VALID_FIELDS)
    assert load_metadata(text) == VALID_FIELDS


def test_dump_rejects_missing_field():
    incomplete = dict(VALID_FIELDS)
    del incomplete["locale"]
    with pytest.raises(ValueError):
        dump_metadata(incomplete)


def test_dump_rejects_unknown_field():
    extra = dict(VALID_FIELDS)
    extra["ai_summary"] = "not allowed"
    with pytest.raises(ValueError):
        dump_metadata(extra)


def test_dump_output_is_deterministic():
    assert dump_metadata(VALID_FIELDS) == dump_metadata(dict(reversed(VALID_FIELDS.items())))
