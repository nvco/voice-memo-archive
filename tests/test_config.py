import json
from pathlib import Path

import pytest

from voice_memo_archive.config import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_RECORDINGS_SOURCE,
    Config,
    load_config,
    save_config,
)
from voice_memo_archive.errors import ConfigError


def test_load_config_missing_file_returns_defaults(tmp_path: Path):
    config = load_config(tmp_path / "config.json")
    assert config == Config()
    assert config.recordings_source == DEFAULT_RECORDINGS_SOURCE
    assert config.archive_root == DEFAULT_ARCHIVE_ROOT
    assert config.schema_version == CURRENT_SCHEMA_VERSION


def test_save_then_load_round_trip(tmp_path: Path):
    path = tmp_path / "config.json"
    original = Config(recordings_source="/custom/source", archive_root="/custom/archive")
    save_config(path, original)
    loaded = load_config(path)
    assert loaded == original


def test_load_config_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_rejects_non_object_json(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_rejects_missing_required_field(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 1, "recordings_source": "/x"}))
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_rejects_future_schema_version(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 99,
                "recordings_source": "/x",
                "archive_root": "/y",
            }
        )
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_save_config_is_atomic_no_leftover_temp_files(tmp_path: Path):
    path = tmp_path / "config.json"
    save_config(path, Config())
    leftovers = [p for p in tmp_path.iterdir() if p != path]
    assert leftovers == []


def test_load_config_without_phase7_fields_uses_defaults(tmp_path: Path):
    # A config.json written before Phase 7 has none of these keys — must
    # still load, with sensible defaults, no migration required.
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"schema_version": 1, "recordings_source": "/x", "archive_root": "/y"})
    )
    config = load_config(path)
    assert config.import_mode == "all"
    assert config.import_since is None
    assert config.setup_completed_at is None


def test_save_then_load_round_trip_with_phase7_fields(tmp_path: Path):
    path = tmp_path / "config.json"
    original = Config(
        import_mode="date",
        import_since="2024-06-01",
        setup_completed_at="2024-06-15T12:00:00Z",
    )
    save_config(path, original)
    assert load_config(path) == original


def test_load_config_ignores_legacy_schedule_fields(tmp_path: Path):
    # A config.json written before background automation was removed
    # (tasks/050-...md) has schedule_mode/scan_interval_seconds keys —
    # loading it must not fail or resurrect them, just ignore them.
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": "/x",
                "archive_root": "/y",
                "schedule_mode": "monitoring",
                "scan_interval_seconds": 900,
            }
        )
    )
    config = load_config(path)
    assert not hasattr(config, "schedule_mode")
    assert not hasattr(config, "scan_interval_seconds")


def test_load_config_rejects_unknown_import_mode(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": "/x",
                "archive_root": "/y",
                "import_mode": "sometimes",
            }
        )
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_rejects_malformed_import_since(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": "/x",
                "archive_root": "/y",
                "import_since": "not-a-date",
            }
        )
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_rejects_malformed_setup_completed_at(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": "/x",
                "archive_root": "/y",
                "setup_completed_at": "not-a-timestamp",
            }
        )
    )
    with pytest.raises(ConfigError):
        load_config(path)
