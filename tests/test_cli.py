from voice_memo_archive.cli import build_parser, main


def test_scan_reports_not_yet_implemented(capsys, tmp_path):
    exit_code = main(
        ["scan", "--config", str(tmp_path / "config.json"), "--state", str(tmp_path / "state.json")]
    )
    assert exit_code == 1
    assert "not yet implemented" in capsys.readouterr().err


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
