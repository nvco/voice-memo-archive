from voice_memo_archive.errors import ArchiveError, ErrorCategory, ScanLockHeldError


def test_archive_error_str_omits_detail():
    err = ArchiveError(
        ErrorCategory.ARCHIVE_WRITE_FAILED,
        "failed to write file",
        detail={"path": "~/secret/path", "errno": 13},
    )
    rendered = str(err)
    assert "failed to write file" in rendered
    assert "secret" not in rendered
    assert err.detail == {"path": "~/secret/path", "errno": 13}


def test_scan_lock_held_error_category():
    err = ScanLockHeldError("a scan is already in progress")
    assert err.category is ErrorCategory.SCAN_LOCK_HELD


def test_every_category_is_a_distinct_string_value():
    values = [category.value for category in ErrorCategory]
    assert len(values) == len(set(values))
