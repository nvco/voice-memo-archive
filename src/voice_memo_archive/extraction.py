"""Native transcript extraction (Phase 4).

Implements the two container lookup paths confirmed on real samples in
tasks/005-platform-feasibility-and-data-contract.md's Findings:

- `.m4a`: a direct `tsrp` box under `moov/trak/udta`, payload = transcript
  JSON directly, no indirection.
- `.qta`: a `meta` box directly under `trak` (no ISO full-box
  version/flags header — a QuickTime-classic-style meta, not an isom-style
  one), whose `keys` table maps the `mdta`/`com.apple.VoiceMemos.tsrp`
  entry to an `ilst` item; that item's `data` box holds the transcript
  JSON (ignore its type-indicator field, which reads 0/"reserved" even for
  JSON text — identify the value by key name, not that field).

Per the open item in tasks/005-...md ("did not verify the track-selection
logic against a sample where track order might differ"), this searches
every `trak` rather than assuming the first one.

Only box headers are ever read for boxes we don't need content from —
`mdat` (the audio payload) is seeked past, never read. The only payload
reads are the `tsrp`/`keys`/`data` box bodies themselves, each bounded by
`_MAX_METADATA_READ` so a corrupted container can't force an unbounded
read.

This module makes no network call and never touches Voice Memos' private
database — see `tests/test_extraction.py`'s
`test_extraction_never_opens_a_socket` for a runtime check of the former.

**Refinement of the Phase 1 draft contract** (recorded here since Phase 1
left these open — see tasks/005-...md's "Draft extraction result
contract"): `malformed` now covers container-structure parse failures
(truncated/corrupt atoms) in addition to transcript-JSON parse failures,
since the draft's original wording ("the transcript entry was found, but
its bytes did not parse...") didn't have a bucket for a broken container
that never yields a transcript entry to examine in the first place; and
`locale` is populated for `incomplete`, not just `ok`/`empty`, since an
`incomplete` result by definition already parsed the top-level JSON
(including `locale`) successfully — only the `runs`/`attributeTable`
invariant failed.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from .paths import SUPPORTED_EXTENSIONS

EXTRACTION_FORMAT_VERSION = 1

# Only the tsrp/keys/data boxes are ever read in full; this bounds those
# reads so a corrupted container claiming an absurd size can't force an
# unbounded read. Every other box (including mdat) is only ever seeked
# past by its header.
_MAX_METADATA_READ = 10 * 1024 * 1024  # 10 MiB


class ExtractionStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    ABSENT = "absent"
    UNREADABLE = "unreadable"
    MALFORMED = "malformed"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ExtractionResult:
    status: ExtractionStatus
    source_format: str | None = None
    transcript_text: str | None = None
    timing: tuple[tuple[float, float], ...] | None = None
    locale: str | None = None
    extraction_format_version: int = EXTRACTION_FORMAT_VERSION


class _ContainerParseError(Exception):
    """Internal signal for a bounded, contained parse failure -> `malformed`."""


@dataclass(frozen=True)
class _Box:
    type: bytes
    body_start: int
    body_end: int


def _iter_boxes(file: BinaryIO, start: int, end: int):
    offset = start
    while offset < end:
        file.seek(offset)
        header = file.read(8)
        if len(header) < 8:
            raise _ContainerParseError("truncated box header")
        size, box_type = struct.unpack(">I4s", header)
        header_len = 8
        if size == 1:
            ext = file.read(8)
            if len(ext) < 8:
                raise _ContainerParseError("truncated 64-bit box size")
            (size,) = struct.unpack(">Q", ext)
            header_len = 16
        elif size == 0:
            size = end - offset
        if size < header_len:
            raise _ContainerParseError("box size smaller than its own header")
        body_start = offset + header_len
        body_end = min(offset + size, end)
        yield _Box(type=box_type, body_start=body_start, body_end=body_end)
        offset += size


def _find_box(file: BinaryIO, box_type: bytes, start: int, end: int) -> _Box | None:
    for box in _iter_boxes(file, start, end):
        if box.type == box_type:
            return box
    return None


def _find_all_boxes(file: BinaryIO, box_type: bytes, start: int, end: int) -> list[_Box]:
    return [box for box in _iter_boxes(file, start, end) if box.type == box_type]


def _read_bounded(file: BinaryIO, box: _Box) -> bytes:
    length = box.body_end - box.body_start
    if length < 0 or length > _MAX_METADATA_READ:
        raise _ContainerParseError("metadata box exceeds bounded read size")
    file.seek(box.body_start)
    data = file.read(length)
    if len(data) != length:
        raise _ContainerParseError("truncated box body")
    return data


def _find_tsrp_payload(file: BinaryIO, trak: _Box) -> bytes | None:
    udta = _find_box(file, b"udta", trak.body_start, trak.body_end)
    if udta is None:
        return None
    tsrp = _find_box(file, b"tsrp", udta.body_start, udta.body_end)
    if tsrp is None:
        return None
    return _read_bounded(file, tsrp)


def _find_metadata_keyed_payload(file: BinaryIO, trak: _Box) -> bytes | None:
    meta = _find_box(file, b"meta", trak.body_start, trak.body_end)
    if meta is None:
        return None
    keys_box = _find_box(file, b"keys", meta.body_start, meta.body_end)
    ilst_box = _find_box(file, b"ilst", meta.body_start, meta.body_end)
    if keys_box is None or ilst_box is None:
        return None

    key_index = _find_key_index(file, keys_box, b"mdta", b"com.apple.VoiceMemos.tsrp")
    if key_index is None:
        return None

    for item in _iter_boxes(file, ilst_box.body_start, ilst_box.body_end):
        (item_index,) = struct.unpack(">I", item.type)
        if item_index != key_index:
            continue
        data_box = _find_box(file, b"data", item.body_start, item.body_end)
        if data_box is None:
            return None
        return _read_data_box_payload(file, data_box)
    return None


def _find_key_index(
    file: BinaryIO, keys_box: _Box, namespace: bytes, key_value: bytes
) -> int | None:
    payload = _read_bounded(file, keys_box)
    if len(payload) < 8:
        raise _ContainerParseError("keys box too short for its header")
    # 4 bytes version+flags (full box), 4 bytes entry_count.
    (entry_count,) = struct.unpack(">I", payload[4:8])
    offset = 8
    for index in range(1, entry_count + 1):
        if offset + 8 > len(payload):
            raise _ContainerParseError("truncated keys entry")
        (entry_size,) = struct.unpack(">I", payload[offset : offset + 4])
        entry_namespace = payload[offset + 4 : offset + 8]
        if entry_size < 8 or offset + entry_size > len(payload):
            raise _ContainerParseError("malformed keys entry size")
        entry_value = payload[offset + 8 : offset + entry_size]
        if entry_namespace == namespace and entry_value == key_value:
            return index
        offset += entry_size
    return None


def _read_data_box_payload(file: BinaryIO, data_box: _Box) -> bytes:
    payload = _read_bounded(file, data_box)
    if len(payload) < 8:
        raise _ContainerParseError("data box too short for its header")
    # First 4 bytes: type indicator (ignored — observed 0/"reserved" even
    # for JSON text; identify by key name, not this field). Next 4 bytes:
    # locale/country indicator (ignored, unused here).
    return payload[8:]


def _find_transcript_payload(file: BinaryIO, moov: _Box) -> bytes | None:
    for trak in _find_all_boxes(file, b"trak", moov.body_start, moov.body_end):
        payload = _find_tsrp_payload(file, trak)
        if payload is not None:
            return payload
        payload = _find_metadata_keyed_payload(file, trak)
        if payload is not None:
            return payload
    return None


def extract_transcript(recording_path: Path) -> ExtractionResult:
    extension = recording_path.suffix.lstrip(".").lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return ExtractionResult(
            status=ExtractionStatus.UNSUPPORTED, source_format=extension or None
        )

    try:
        with recording_path.open("rb") as file:
            file.seek(0, 2)
            file_size = file.tell()
            try:
                moov = _find_box(file, b"moov", 0, file_size)
                if moov is None:
                    return ExtractionResult(
                        status=ExtractionStatus.MALFORMED, source_format=extension
                    )
                payload = _find_transcript_payload(file, moov)
            except _ContainerParseError:
                return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)
    except OSError:
        return ExtractionResult(status=ExtractionStatus.UNREADABLE, source_format=extension)

    if payload is None:
        return ExtractionResult(status=ExtractionStatus.ABSENT, source_format=extension)

    return _parse_transcript_json(payload, extension)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_transcript_json(payload: bytes, extension: str) -> ExtractionResult:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)

    if not isinstance(document, dict):
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)

    locale = document.get("locale")
    if not isinstance(locale, dict) or not isinstance(locale.get("identifier"), str):
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)
    locale_identifier = locale["identifier"]

    if "attributedString" not in document:
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)
    attributed_string = document["attributedString"]

    if isinstance(attributed_string, str):
        if attributed_string == "":
            return ExtractionResult(
                status=ExtractionStatus.EMPTY, source_format=extension, locale=locale_identifier
            )
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)

    if not isinstance(attributed_string, dict):
        return ExtractionResult(status=ExtractionStatus.MALFORMED, source_format=extension)

    return _parse_attributed_string(attributed_string, extension, locale_identifier)


def _incomplete(extension: str, locale_identifier: str) -> ExtractionResult:
    return ExtractionResult(
        status=ExtractionStatus.INCOMPLETE, source_format=extension, locale=locale_identifier
    )


def _parse_attributed_string(
    attributed_string: dict, extension: str, locale_identifier: str
) -> ExtractionResult:
    runs = attributed_string.get("runs")
    attribute_table = attributed_string.get("attributeTable")
    if not isinstance(runs, list) or not isinstance(attribute_table, list):
        return _incomplete(extension, locale_identifier)
    if len(runs) != 2 * len(attribute_table):
        return _incomplete(extension, locale_identifier)

    time_ranges: list[tuple[float, float]] = []
    for entry in attribute_table:
        if not isinstance(entry, dict):
            return _incomplete(extension, locale_identifier)
        time_range = entry.get("timeRange")
        if (
            not isinstance(time_range, list)
            or len(time_range) != 2
            or not all(_is_number(v) for v in time_range)
            or time_range[0] > time_range[1]
        ):
            return _incomplete(extension, locale_identifier)
        time_ranges.append((float(time_range[0]), float(time_range[1])))

    for earlier, later in zip(time_ranges, time_ranges[1:]):
        if later[0] < earlier[0]:
            return _incomplete(extension, locale_identifier)

    texts: list[str] = []
    timing: list[tuple[float, float]] = []
    for text, index in zip(runs[0::2], runs[1::2]):
        if not isinstance(text, str) or not _is_plain_int(index):
            return _incomplete(extension, locale_identifier)
        if index < 0 or index >= len(time_ranges):
            return _incomplete(extension, locale_identifier)
        texts.append(text)
        timing.append(time_ranges[index])

    return ExtractionResult(
        status=ExtractionStatus.OK,
        source_format=extension,
        transcript_text="".join(texts),
        timing=tuple(timing),
        locale=locale_identifier,
    )
