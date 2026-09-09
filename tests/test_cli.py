import json

from voice_memo_archive.cli import build_parser, main


def _write_synthetic_config(tmp_path):
    # Never rely on cli.py's real Application-Support defaults in a test —
    # those point at the real Voice Memos folder on whatever machine runs
    # this suite. Every scan test gets its own empty, synthetic tree.
    recordings_source = tmp_path / "recordings"
    archive_root = tmp_path / "archive"
    recordings_source.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recordings_source": str(recordings_source),
                "archive_root": str(archive_root),
            }
        )
    )
    return config_path


def test_scan_with_no_recordings_reports_nothing_to_do(capsys, tmp_path):
    config_path = _write_synthetic_config(tmp_path)
    exit_code = main(
        ["scan", "--config", str(config_path), "--state", str(tmp_path / "state.json")]
    )
    assert exit_code == 0
    assert "nothing to do" in capsys.readouterr().out


def test_doctor_reports_not_yet_implemented(capsys, tmp_path):
    exit_code = main(["doctor", "--recordings-source", str(tmp_path)])
    assert exit_code == 1
    assert "not yet implemented" in capsys.readouterr().err


def test_parser_requires_a_command():
    parser = build_parser()
    try:
        parser.parse_args([])
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass
