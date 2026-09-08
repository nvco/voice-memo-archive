"""Synthetic ISO-BMFF/QuickTime container builders for extraction tests.

Built from scratch, byte by byte — never derived from a real sample's
actual bytes. Placeholder transcript text only, per `AGENTS.md`'s
local-sample handling rules. Fills the fixture mechanism
`tests/fixtures/synthetic/README.md` deferred to Phase 4.
"""

from __future__ import annotations

import json
import struct


def box(box_type: bytes, body: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(body), box_type) + body


def ftyp_box(brand: bytes = b"M4A ") -> bytes:
    return box(b"ftyp", brand + struct.pack(">I", 0) + brand)


def mdat_box(payload: bytes) -> bytes:
    return box(b"mdat", payload)


def tsrp_box(payload: bytes) -> bytes:
    return box(b"tsrp", payload)


def udta_box(children: bytes) -> bytes:
    return box(b"udta", children)


def trak_box(children: bytes) -> bytes:
    return box(b"trak", children)


def moov_box(children: bytes) -> bytes:
    return box(b"moov", children)


def keys_box(entries: list[tuple[bytes, bytes]]) -> bytes:
    body = struct.pack(">II", 0, len(entries))  # version+flags(4), entry_count(4)
    for namespace, key_value in entries:
        entry_size = 8 + len(key_value)
        body += struct.pack(">I4s", entry_size, namespace) + key_value
    return box(b"keys", body)


def data_box(payload: bytes, *, type_indicator: int = 0, locale_indicator: int = 0) -> bytes:
    return box(b"data", struct.pack(">II", type_indicator, locale_indicator) + payload)


def ilst_item(index: int, data: bytes) -> bytes:
    return box(struct.pack(">I", index), data)


def ilst_box(items: bytes) -> bytes:
    return box(b"ilst", items)


def meta_box_no_header(children: bytes) -> bytes:
    # QuickTime-classic-style meta: no ISO full-box version/flags header,
    # per tasks/005-...md's Findings for `.qta`.
    return box(b"meta", children)


def make_transcript_json(
    *,
    locale: str = "en_US",
    langs: list[str] | None = None,
    runs_texts: list[str] | None = None,
    time_ranges: list[list[float]] | None = None,
) -> bytes:
    if runs_texts is None:
        runs_texts = ["sample", " transcript", " text"]
    if time_ranges is None:
        time_ranges = [[0.0, 0.5], [0.5, 1.2], [1.2, 1.8]]
    attribute_table = [{"timeRange": tr} for tr in time_ranges]
    runs: list[object] = []
    for index, text in enumerate(runs_texts):
        runs.extend([text, index])
    document = {
        "locale": {
            "identifier": locale,
            "preferences": {
                "locale": locale,
                "langs": langs or [locale.replace("_", "-")],
                "temp": 0,
            },
            "current": 0,
        },
        "attributedString": {"runs": runs, "attributeTable": attribute_table},
    }
    return json.dumps(document).encode("utf-8")


def make_empty_transcript_json(*, locale: str = "en_US") -> bytes:
    document = {
        "locale": {
            "identifier": locale,
            "preferences": {"locale": locale, "langs": [locale.replace("_", "-")], "temp": 0},
            "current": 0,
        },
        "attributedString": "",
    }
    return json.dumps(document).encode("utf-8")


def build_m4a_container(
    transcript_json: bytes | None, *, mdat_payload: bytes = b"\x00" * 1024
) -> bytes:
    udta_children = tsrp_box(transcript_json) if transcript_json is not None else b""
    moov = moov_box(trak_box(udta_box(udta_children)))
    return ftyp_box(b"M4A ") + moov + mdat_box(mdat_payload)


def _qta_metadata_trak(transcript_json: bytes | None) -> bytes:
    if transcript_json is None:
        return trak_box(b"")
    keys = keys_box([(b"mdta", b"com.apple.VoiceMemos.tsrp")])
    data = data_box(transcript_json)
    ilst = ilst_box(ilst_item(1, data))
    meta = meta_box_no_header(keys + ilst)
    return trak_box(meta)


def build_qta_container(
    transcript_json: bytes | None,
    *,
    mdat_payload: bytes = b"\x00" * 1024,
    metadata_on_second_track: bool = False,
) -> bytes:
    metadata_trak = _qta_metadata_trak(transcript_json)
    empty_trak = trak_box(b"")
    traks = empty_trak + metadata_trak if metadata_on_second_track else metadata_trak + empty_trak
    moov = moov_box(traks)
    return ftyp_box(b"qt  ") + moov + mdat_box(mdat_payload)
