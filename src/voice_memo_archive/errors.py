"""Structured error taxonomy shared across every module.

`message` must always be safe to print or log by default: no transcript
text, no recording titles, no absolute paths. Use `paths.redact_home_path`
before including any filesystem path in a message. Arbitrary, potentially
sensitive context belongs in `detail`, which callers must opt into logging
explicitly — it is never included by `ArchiveError.__str__`.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    # Source-recording access (Phase 3/4).
    SOURCE_UNREADABLE = "source_unreadable"
    SOURCE_UNSUPPORTED = "source_unsupported"

    # Native transcript extraction result, mirrors the Phase 1 contract's
    # `status` classifications (see tasks/005-...md "Draft extraction
    # result contract").
    TRANSCRIPT_ABSENT = "transcript_absent"
    TRANSCRIPT_EMPTY = "transcript_empty"
    TRANSCRIPT_MALFORMED = "transcript_malformed"
    TRANSCRIPT_INCOMPLETE = "transcript_incomplete"

    # Configuration and operational state (Phase 2).
    CONFIG_INVALID = "config_invalid"
    STATE_INVALID = "state_invalid"
    STATE_MIGRATION_FAILED = "state_migration_failed"

    # Scan coordination and archive writing (Phase 2/5/6).
    SCAN_LOCK_HELD = "scan_lock_held"
    ARCHIVE_WRITE_FAILED = "archive_write_failed"
    ARCHIVE_CONFLICT = "archive_conflict"


class ArchiveError(Exception):
    """Base exception for all taxonomy errors.

    `detail` is a free-form dict for developer diagnosis (e.g. an errno, a
    redacted path, a byte offset). It is kept separate from `message`
    precisely so a caller can choose not to log it.
    """

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        detail: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.detail = detail or {}

    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class ConfigError(ArchiveError):
    pass


class StateError(ArchiveError):
    pass


class ScanLockHeldError(ArchiveError):
    def __init__(self, message: str, detail: dict[str, object] | None = None) -> None:
        super().__init__(ErrorCategory.SCAN_LOCK_HELD, message, detail)
