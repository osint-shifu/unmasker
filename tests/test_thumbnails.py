"""The preview that still shows what was cropped out.

A photograph carries a small copy of itself in its EXIF, for a camera's screen
and a file browser's grid. **Cropping the photograph does not regenerate it.**
Cut a face, a name or a plate out of a picture and the preview in the file
still shows the frame you cut it out of.

Not a reading of the specification: ImageMagick carries the old thumbnail
through a crop **unasked**, which is how the specimen is built. A person
opening the file cannot see the cropped strip; every EXIF reader can.

## Why the shape and not the pixels

Comparing the preview to the picture properly means decoding two JPEGs, which
means a second runtime dependency, which `CONTRIBUTING.md` says has to be
argued for in writing. It does not have to be: a JPEG states its own dimensions
in a marker, and so does the thumbnail, because the thumbnail is a JPEG too.
**A preview a different shape from its picture was not made from it** - and
that is bytes, not pixels.

So the default finding is `circumstantial` and reads the headers. `--ocr`,
which already exists and already costs two binaries, does the rest: read the
preview back and report what is legible in it and absent from the picture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unmasker.cli import collect
from unmasker.findings import Basis
from unmasker.readers import read

SPECIMENS = Path(__file__).parent / "specimens" / "jpeg"

STALE = SPECIMENS / "imagemagick-stale-thumbnail.jpg"
REGENERATED = SPECIMENS / "imagemagick-thumbnail-regenerated.jpg"
NO_THUMBNAIL = SPECIMENS / "imagemagick-no-thumbnail.jpg"

CROPPED_AWAY = "WITNESS"


def findings_for(path: Path, ocr: bool = False):
    return collect(read(path), ocr=ocr)


def by_detector(path: Path, name: str, ocr: bool = False):
    return [f for f in findings_for(path, ocr=ocr) if f.detector == name]


# --------------------------------------------------------------------------
# a photograph is a document this tool reads now
# --------------------------------------------------------------------------


def test_a_jpeg_is_read():
    assert read(STALE).kind == "image"


def test_a_jpeg_is_dispatched_by_its_bytes_not_its_name(tmp_path):
    """Dispatch is by content everywhere else in this tool, and a photograph
    saved as `scan.txt` is still a photograph."""
    disguised = tmp_path / "scan.txt"
    disguised.write_bytes(STALE.read_bytes())
    assert read(disguised).kind == "image"


def test_a_photograph_has_no_text_to_search_and_says_so():
    """`CONTRIBUTING.md`: nothing found has two meanings. A picture has no text
    layer, and a reader must not be told it was searched and came back clean."""
    extraction = read(STALE)
    assert not extraction.has_text
    assert any("no text" in remark.lower() for remark in extraction.remarks)


# --------------------------------------------------------------------------
# the stale preview
# --------------------------------------------------------------------------


def test_the_stale_thumbnail_is_reported():
    (found,) = by_detector(STALE, "stale-thumbnail")
    assert found.basis is Basis.CIRCUMSTANTIAL


def test_it_states_both_shapes():
    """A reader has to be able to check the claim without the tool, and the two
    shapes are the whole of the evidence."""
    (found,) = by_detector(STALE, "stale-thumbnail")
    assert "800" in found.summary and "420" in found.summary
    assert "160" in found.summary and "120" in found.summary


def test_the_human_column_is_the_picture_and_the_machine_column_the_preview():
    (found,) = by_detector(STALE, "stale-thumbnail")
    assert "800" in found.human_sees
    assert "160" in found.machine_reads


def test_a_regenerated_thumbnail_is_not_reported():
    """The control, and the reason this detector is worth having rather than
    firing on every photograph ever cropped."""
    assert by_detector(REGENERATED, "stale-thumbnail") == []


def test_a_photograph_with_no_thumbnail_is_not_reported():
    """Most photographs on the web carry none, and their absence is not a
    finding about anything.

    Read from a committed specimen rather than built here. The first version
    shelled out to ImageMagick, which no CI runner has - and on Windows finds
    the NTFS `convert` instead and fails with exit status 4 rather than
    skipping. CONTRIBUTING.md already names that failure once.
    """
    assert by_detector(NO_THUMBNAIL, "stale-thumbnail") == []


def test_a_photograph_with_no_thumbnail_says_there_was_nothing_to_compare():
    """The stronger half, and the one that matters: silence here has to mean
    *there was nothing to compare*, not *compared and found nothing*. A reader
    who cannot tell those apart has drawn a conclusion the tool never made."""
    remarks = read(NO_THUMBNAIL).remarks

    assert any("no preview" in remark for remark in remarks), remarks


# --------------------------------------------------------------------------
# reading the preview back
# --------------------------------------------------------------------------

ocr_only = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"),
    reason="tesseract is not installed",
)


@ocr_only
def test_ocr_reports_what_is_legible_in_the_preview_and_not_in_the_picture():
    """The strong version of the same claim: not merely that the preview is a
    different shape, but that it still spells the line that was cut."""
    found = by_detector(STALE, "unrendered-text", ocr=True)
    assert any(CROPPED_AWAY in f.machine_reads for f in found)


@ocr_only
def test_ocr_does_not_report_what_is_on_the_picture_too():
    """The headline survives the crop and is in both. Reporting it would be
    calling the visible photograph a concealment."""
    found = by_detector(STALE, "unrendered-text", ocr=True)
    assert not any("Board" in f.machine_reads for f in found)


@ocr_only
def test_ocr_stays_silent_on_the_control():
    assert by_detector(REGENERATED, "unrendered-text", ocr=True) == []


def test_without_ocr_nothing_claims_to_have_read_the_preview():
    """The header comparison says the shapes disagree and no more. Claiming to
    know what is *in* the preview without having looked would be the tool
    outrunning its own evidence."""
    for finding in findings_for(STALE):
        assert CROPPED_AWAY not in finding.machine_reads


# --------------------------------------------------------------------------
# broken and hostile files
# --------------------------------------------------------------------------


def test_a_truncated_jpeg_is_refused_rather_than_guessed_at(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(STALE.read_bytes()[:20])
    from unmasker.readers import UnreadableFile

    with pytest.raises(UnreadableFile):
        read(broken)


def test_a_jpeg_whose_thumbnail_offset_points_outside_the_file_is_not_a_crash(tmp_path):
    """Every byte here came out of a file somebody else wrote."""
    data = bytearray(STALE.read_bytes())
    # Corrupt the middle of the EXIF block rather than the markers around it.
    for i in range(40, 120):
        data[i] = 0xFF
    hostile = tmp_path / "hostile.jpg"
    hostile.write_bytes(bytes(data))
    try:
        findings_for(hostile)
    except Exception as exc:  # noqa: BLE001 - the assertion is that there is none
        raise AssertionError(f"a malformed EXIF block raised {exc!r}") from exc


# --------------------------------------------------------------------------
# bytes written by whoever is being investigated
#
# `SECURITY.md` says the threat model here is the parser, and these are the
# bounds checks that make that claim true. No specimen can reach them: a file
# ImageMagick wrote is well formed by construction, so the offsets are crafted.
#
# Mutation testing is what said so - each of these was a guard nothing held.
# --------------------------------------------------------------------------

import struct  # noqa: E402

from unmasker.jpeg import dimensions  # noqa: E402
from unmasker.jpeg import read as read_jpeg  # noqa: E402


def sof(width: int, height: int) -> bytes:
    return b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x00\x00\x00"


def jpeg(*segments: bytes, scan: bytes = b"") -> bytes:
    return b"\xff\xd8" + b"".join(segments) + b"\xff\xda\x00\x02" + scan + b"\xff\xd9"


def exif(payload: bytes) -> bytes:
    body = b"Exif\x00\x00" + payload
    return b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body


def tiff(entries: list[tuple[int, int]], count: int | None = None) -> bytes:
    """A TIFF block whose second IFD carries the tags given, with the entry
    count settable independently so it can be made to lie."""
    header = b"II" + struct.pack("<HI", 42, 8)
    ifd0 = struct.pack("<H", 0) + struct.pack("<I", 8 + 2 + 4)
    written = struct.pack("<H", count if count is not None else len(entries))
    for tag, value in entries:
        written += struct.pack("<HHII", tag, 4, 1, value)
    return header + ifd0 + written + struct.pack("<I", 0)


def test_the_walk_stops_at_the_scan_instead_of_reading_compressed_data():
    """`0xFFC0` occurs inside compressed data constantly. A reader that scanned
    for the marker bytes rather than walking the segment chain would find one
    of those and report a picture the size of noise."""
    data = jpeg(scan=sof(9999, 9999))
    assert dimensions(data) is None


def test_a_thumbnail_offset_past_the_end_of_the_block_is_refused():
    """Every offset came out of the file being examined."""
    payload = tiff([(0x0201, 0xFFFFFF00), (0x0202, 64)])
    picture = read_jpeg(jpeg(exif(payload), sof(800, 420)))
    assert picture.size is not None
    assert picture.thumbnail is None


def test_a_thumbnail_length_longer_than_the_block_is_refused():
    payload = tiff([(0x0201, 4), (0x0202, 0xFFFFFF00)])
    assert read_jpeg(jpeg(exif(payload), sof(800, 420))).thumbnail is None


def test_an_ifd_claiming_more_entries_than_the_block_holds_is_refused():
    """A count of 65535 asks for 786 kB of entries out of a block that may be
    a hundred bytes long."""
    payload = tiff([(0x0201, 4), (0x0202, 8)], count=0xFFFF)
    assert read_jpeg(jpeg(exif(payload), sof(800, 420))).thumbnail is None


def test_a_thumbnail_that_is_present_and_unreadable_is_not_silence():
    """`CONTRIBUTING.md`: nothing found has two meanings. A preview that is
    there and cannot be measured was not compared, and saying nothing would
    let a reader conclude it matched."""
    payload = tiff([(0x0201, 4), (0x0202, 8)])
    picture = read_jpeg(jpeg(exif(payload), sof(800, 420)))
    assert picture.thumbnail is not None
    assert picture.thumbnail_size is None
    assert any("could not be read" in remark for remark in picture.remarks)


def test_a_word_the_engine_is_unsure_of_is_not_quoted():
    """OCR reports what it half-saw in the paper grain with a confidence of 12,
    and a report that quoted those would be inventing the evidence it exists to
    show."""
    from unmasker.thumbnails import _words

    tsv = (
        "level\tpage\tblock\tpar\tline\tword\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t95.0\tCERTAIN\n"
        "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t12.0\tnoise\n"
    )

    class _Fake:
        stdout = tsv

    import unmasker.thumbnails as module

    original = module.subprocess.run
    module.subprocess.run = lambda *a, **k: _Fake()
    try:
        words, problems = _words(Path("anything.jpg"))
    finally:
        module.subprocess.run = original

    assert words == ["CERTAIN"]
    assert not problems
