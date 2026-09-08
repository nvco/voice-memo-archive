import io
import json
import socket
import struct
from pathlib import Path

import mp4_builders as mp4

from voice_memo_archive import extraction
from voice_memo_archive.extraction import ExtractionStatus, extract_transcript


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_extract_m4a_ok(tmp_path: Path):
    data = mp4.build_m4a_container(mp4.make_transcript_json())
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.OK
    assert result.source_format == "m4a"
    assert result.transcript_text == "sample transcript text"
    assert result.timing == ((0.0, 0.5), (0.5, 1.2), (1.2, 1.8))
    assert result.locale == "en_US"


def test_extract_qta_ok(tmp_path: Path):
    data = mp4.build_qta_container(mp4.make_transcript_json())
    path = _write(tmp_path, "20240115 143022-A.qta", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.OK
    assert result.source_format == "qta"
    assert result.transcript_text == "sample transcript text"
    assert result.locale == "en_US"


def test_extract_preserves_unicode_text(tmp_path: Path):
    transcript = mp4.make_transcript_json(
        runs_texts=["café", " über", " 日本語", " \U0001f600"],
        time_ranges=[[0.0, 0.2], [0.2, 0.4], [0.4, 0.6], [0.6, 0.8]],
    )
    path = _write(tmp_path, "20240115 143022-A.m4a", mp4.build_m4a_container(transcript))

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.OK
    assert result.transcript_text == "café über 日本語 \U0001f600"


def test_extract_qta_finds_metadata_on_second_track(tmp_path: Path):
    # Regression guard for the open item in tasks/005-...md: don't assume
    # the metadata always sits on the first trak.
    data = mp4.build_qta_container(mp4.make_transcript_json(), metadata_on_second_track=True)
    path = _write(tmp_path, "20240115 143022-A.qta", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.OK
    assert result.transcript_text == "sample transcript text"


def test_extract_empty(tmp_path: Path):
    data = mp4.build_m4a_container(mp4.make_empty_transcript_json())
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.EMPTY
    assert result.transcript_text is None
    assert result.timing is None
    assert result.locale == "en_US"


def test_extract_absent_when_no_transcript_box_anywhere(tmp_path: Path):
    data = mp4.build_m4a_container(None)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.ABSENT
    assert result.locale is None


def test_extract_unreadable_when_file_missing(tmp_path: Path):
    result = extract_transcript(tmp_path / "does-not-exist.m4a")
    assert result.status is ExtractionStatus.UNREADABLE


def test_extract_unsupported_extension(tmp_path: Path):
    path = _write(tmp_path, "20240115 143022-A.txt", b"not a container at all")
    result = extract_transcript(path)
    assert result.status is ExtractionStatus.UNSUPPORTED


def test_extract_malformed_when_no_moov(tmp_path: Path):
    data = mp4.ftyp_box() + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_extract_malformed_when_tsrp_payload_is_not_json(tmp_path: Path):
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(b"not json at all"))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_extract_malformed_when_attributed_string_key_missing(tmp_path: Path):
    payload = b'{"locale": {"identifier": "en_US"}}'
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(payload))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_extract_malformed_when_locale_identifier_missing(tmp_path: Path):
    payload = b'{"locale": {}, "attributedString": ""}'
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(payload))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_extract_malformed_when_attributed_string_is_nonempty_string(tmp_path: Path):
    payload = b'{"locale": {"identifier": "en_US"}, "attributedString": "unexpected"}'
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(payload))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_extract_incomplete_when_runs_length_mismatches_attribute_table(tmp_path: Path):
    transcript = mp4.make_transcript_json()
    document = json.loads(transcript)
    document["attributedString"]["runs"].pop()  # break the 2x invariant
    payload = json.dumps(document).encode("utf-8")
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(payload))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.INCOMPLETE
    assert result.locale == "en_US"


def test_extract_incomplete_when_time_range_is_inverted(tmp_path: Path):
    transcript = mp4.make_transcript_json(time_ranges=[[1.0, 0.5]])
    payload = transcript
    document = json.loads(payload)
    document["attributedString"]["runs"] = ["only run", 0]
    payload = json.dumps(document).encode("utf-8")
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(mp4.tsrp_box(payload))))
    data = mp4.ftyp_box() + moov + mp4.mdat_box(b"\x00" * 16)
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.INCOMPLETE


def test_extract_incomplete_when_attribute_table_not_monotonic(tmp_path: Path):
    transcript = mp4.make_transcript_json(
        runs_texts=["a", " b"], time_ranges=[[5.0, 6.0], [0.0, 1.0]]
    )
    path = _write(
        tmp_path,
        "20240115 143022-A.m4a",
        mp4.build_m4a_container(transcript),
    )

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.INCOMPLETE


def test_extract_malformed_on_truncated_tsrp_box(tmp_path: Path):
    real_payload = mp4.make_transcript_json()
    tsrp = mp4.tsrp_box(real_payload)
    truncated_tsrp = tsrp[:-5]  # box header claims more bytes than are present
    moov = mp4.moov_box(mp4.trak_box(mp4.udta_box(truncated_tsrp)))
    data = mp4.ftyp_box() + moov  # no mdat either, to keep the file short

    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.MALFORMED


def test_moov_lookup_never_reads_mdat_payload():
    class _CountingBytesIO(io.BytesIO):
        def __init__(self, data: bytes) -> None:
            super().__init__(data)
            self.total_read = 0

        def read(self, size: int = -1) -> bytes:
            chunk = super().read(size)
            self.total_read += len(chunk)
            return chunk

    big_mdat_payload = b"\xab" * (2 * 1024 * 1024)
    data = mp4.build_m4a_container(mp4.make_transcript_json(), mdat_payload=big_mdat_payload)

    fake_file = _CountingBytesIO(data)
    box = extraction._find_box(fake_file, b"moov", 0, len(data))

    assert box is not None
    assert fake_file.total_read < 10_000


def test_extraction_never_opens_a_socket(tmp_path: Path, monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("extraction must never open a network socket")

    monkeypatch.setattr(socket, "socket", _forbidden)

    data = mp4.build_m4a_container(mp4.make_transcript_json())
    path = _write(tmp_path, "20240115 143022-A.m4a", data)

    result = extract_transcript(path)

    assert result.status is ExtractionStatus.OK


def test_extraction_module_has_no_sqlite_import():
    import voice_memo_archive.extraction as extraction_module

    source = Path(extraction_module.__file__).read_text()
    assert "sqlite3" not in source
    assert "CloudRecordings.db" not in source


def test_box_header_with_64_bit_size_is_parsed(tmp_path: Path):
    # Exercise the size==1 (64-bit extended size) branch directly, since no
    # real sample this small would ever need one.
    payload = b"synthetic-body"
    header = struct.pack(">I4sQ", 1, b"free", 16 + len(payload))
    data = header + payload
    fake_file = io.BytesIO(data)

    found = extraction._find_box(fake_file, b"free", 0, len(data))

    assert found is not None
    assert found.body_end - found.body_start == len(payload)
