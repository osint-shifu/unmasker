"""The `WordDocument` stream: where a .doc actually keeps its text.

Every number here was read out of the specimens before the reader existed,
which for this format matters more than usual. Three things the specification
does not warn about, and all three came out of real LibreOffice output:

**The main story is not the document.** A .doc lays its text end to end in one
character-position space and the FIB says how long each part is: `ccpText`,
then footnotes, headers and footers, comments, endnotes, text boxes. In
`libreoffice-writer-word97-stories.doc` the main story is 267 characters of
504. A reader that took `[0, ccpText)` would search just over half the file and
then report that it had searched it - and the part it skipped holds a comment
naming a bidder and a header marked *internal circulation only*.

**A hyperlink is a field, not a run.** The bytes hold `0x13 HYPERLINK "..."
0x14 published summary 0x15`: an instruction, a separator, a result. Only the
result is on the page. Concatenating the run would put a URL into the visible
text, and every detector downstream would then be told a person could read it.

**The text is UTF-16 even when it is all ASCII.** The specification presents
the compressed 8-bit piece as the ordinary case. LibreOffice never writes one.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from unmasker.ole2 import CompoundFile
from unmasker.word import NotAWordDocument, read_word

SPECIMENS = Path(__file__).parent / "specimens" / "doc"
PLAIN = SPECIMENS / "libreoffice-writer-word97.doc"
STORIES = SPECIMENS / "libreoffice-writer-word97-stories.doc"
MARKS = SPECIMENS / "libreoffice-writer-word97-marks.doc"


@pytest.fixture
def stories():
    return read_word(CompoundFile(STORIES.read_bytes()))


@pytest.fixture
def plain():
    return read_word(CompoundFile(PLAIN.read_bytes()))


class Stub:
    """A compound file with the streams a test names and nothing else.

    Used only where what is under test is a flag in the FIB rather than the
    parsing of a real producer's bytes - an encryption bit, a version too old
    to read. The bytes still come from the specimen; only the header is moved.
    """

    def __init__(self, **streams: bytes) -> None:
        self._streams = streams

    @property
    def names(self):
        return tuple(self._streams)

    def read(self, name: str) -> bytes:
        return self._streams[name]


def patched(offset: int, value: bytes, stream: str = "WordDocument") -> Stub:
    """The stories specimen with `value` written over `offset` of `stream`."""
    compound = CompoundFile(STORIES.read_bytes())
    held = {name: compound.read(name) for name in compound.names}
    blob = bytearray(held[stream])
    blob[offset : offset + len(value)] = value
    held[stream] = bytes(blob)
    return Stub(**held)


# --- what the reader must not miss -----------------------------------------


def test_the_main_story_is_not_the_document(stories):
    """The reason this module exists. `ccpText` is 267 of 504 characters."""
    whole = "".join(story.text for story in stories.stories) + "".join(
        comment.text for comment in stories.comments
    )
    assert len(whole) > 300, "only the main story was read"


def test_every_story_the_file_declares_comes_back(stories):
    assert [story.name for story in stories.stories] == [
        "the document",
        "footnotes",
        "headers and footers",
        "text boxes",
    ]


def test_the_header_is_read_and_it_is_the_part_worth_reading(stories):
    headers = next(s for s in stories.stories if s.name == "headers and footers")
    assert "internal circulation only" in headers.text
    assert "reviewed by the panel secretary" in headers.text


def test_the_footnote_is_read(stories):
    footnotes = next(s for s in stories.stories if s.name == "footnotes")
    assert "the second bidder withdrew before scoring" in footnotes.text


def test_the_text_box_is_read(stories):
    boxes = next(s for s in stories.stories if s.name == "text boxes")
    assert "figures not yet approved" in boxes.text


# --- comments ---------------------------------------------------------------


def test_a_comment_is_not_visible_text(stories):
    """It must never reach the stories, where it would be searched as though a
    reader could see it - and then reported as showing what it says."""
    visible = "".join(story.text for story in stories.stories)
    assert "we should not name the second bidder" not in visible


def test_a_comment_comes_back_with_the_name_the_file_puts_on_it(stories):
    assert len(stories.comments) == 1
    comment = stories.comments[0]
    assert comment.text == "Comment: we should not name the second bidder here."
    assert comment.author == "Halina Probna-Test"
    assert comment.date is None, "an ATRD of this size carries no date"


# --- fields -----------------------------------------------------------------


def test_a_field_shows_its_result_and_not_its_instruction(stories):
    body = next(s for s in stories.stories if s.name == "the document")
    assert "published summary" in body.text
    assert "HYPERLINK" not in body.text
    assert "internal.example.invalid" not in body.text


def test_the_instruction_is_kept_rather_than_dropped(stories):
    """The URL is the evidence. Excluding it from the visible text is right;
    losing it would be the tool failing to report what it just read."""
    assert len(stories.fields) == 1
    assert "internal.example.invalid/tender/2019/final-scores" in stories.fields[0].instruction
    assert stories.fields[0].result == "published summary"


# --- the format's own punctuation -------------------------------------------


def test_table_cell_marks_do_not_reach_the_text(stories):
    body = next(s for s in stories.stories if s.name == "the document")
    assert "\x07" not in body.text
    assert "Bidder" in body.text and "Wykonawca A" in body.text
    assert "Bidder Score" not in body.text, "cells must not run together"


def test_anchors_and_reference_marks_do_not_reach_the_text(stories):
    """0x02 footnote reference, 0x05 comment anchor, 0x08 drawn object. They
    are the format's punctuation, like a `<w:p>` tag, and reporting one as an
    invisible character would be this tool inventing a finding."""
    body = next(s for s in stories.stories if s.name == "the document")
    assert not set(body.text) & {"\x01", "\x02", "\x05", "\x07", "\x08", "\x13", "\x14", "\x15"}


def test_characters_outside_ascii_survive_the_decode(stories):
    body = next(s for s in stories.stories if s.name == "the document")
    assert "Zamowienie rozstrzygniete" in body.text


def test_a_document_with_one_story_still_reads(plain):
    assert [s.name for s in plain.stories] == ["the document"]
    assert "The contract has been awarded" in plain.stories[0].text
    assert plain.comments == ()


# --- the piece table --------------------------------------------------------


def test_a_compressed_piece_decodes_as_eight_bit_text():
    """Nothing on this machine writes one.

    The specification presents the 8-bit piece as the ordinary case and
    LibreOffice never writes it, so this rewrites a real file's piece table to
    point at 8-bit text rather than asserting against a fixture built from the
    specification. What is under test is one branch; everything around it -
    the FIB, the Clx, the story lengths - is still the producer's.
    """
    compound = CompoundFile(STORIES.read_bytes())
    word = bytearray(compound.read("WordDocument"))
    table = bytearray(compound.read("1Table"))

    fc_clx, _ = struct.unpack("<II", word[0x9A + 66 * 4 : 0x9A + 68 * 4])
    body = "Compressed. The 8-bit piece a producer here never writes.\r"

    # One story, one piece, written where the real one pointed.
    struct.pack_into("<I", word, 0x4C, len(body))          # ccpText
    struct.pack_into("<7I", word, 0x50, *([0] * 7))        # every other story
    word[2048 : 2048 + len(body)] = body.encode("cp1252")

    plc = struct.pack("<II", 0, len(body)) + struct.pack(
        "<HIH", 0, 0x40000000 | (2048 << 1), 0
    )
    table[fc_clx : fc_clx + 5 + len(plc)] = (
        b"\x02" + struct.pack("<I", len(plc)) + plc
    )

    record = read_word(Stub(WordDocument=bytes(word), **{"1Table": bytes(table)}))
    assert record.stories[0].text.strip() == body.strip()


def test_a_piece_table_pointing_past_the_stream_is_refused_not_guessed_at():
    compound = CompoundFile(STORIES.read_bytes())
    word = bytearray(compound.read("WordDocument"))
    table = bytearray(compound.read("1Table"))
    fc_clx, _ = struct.unpack("<II", word[0x9A + 66 * 4 : 0x9A + 68 * 4])
    plc = struct.pack("<II", 0, 40) + struct.pack("<HIH", 0, 1 << 29, 0)
    table[fc_clx : fc_clx + 5 + len(plc)] = b"\x02" + struct.pack("<I", len(plc)) + plc

    with pytest.raises(NotAWordDocument):
        read_word(Stub(WordDocument=bytes(word), **{"1Table": bytes(table)}))


# --- what cannot be read, said rather than passed off as nothing ------------


def test_an_encrypted_document_says_so_rather_than_reporting_no_text():
    """The distinction the whole tool is built on, applied to itself: a file
    whose text is encrypted was not searched and did not come back clean."""
    flags, = struct.unpack("<H", CompoundFile(STORIES.read_bytes()).read("WordDocument")[10:12])
    record = read_word(patched(10, struct.pack("<H", flags | 0x0100)))

    assert record.encrypted is True
    assert record.stories == ()
    assert any("encrypted" in remark for remark in record.remarks)


def test_a_word_6_file_is_refused_rather_than_read_at_the_wrong_offsets():
    """Word 6 and 95 have no FibRgFcLcb97, so the offset this reader uses for
    the piece table lands in the middle of something else. Reading it anyway
    would produce text out of unrelated bytes, which is the one thing this
    tool must not do."""
    with pytest.raises(NotAWordDocument):
        read_word(patched(2, struct.pack("<H", 101)))


def test_a_file_with_no_table_stream_is_refused():
    compound = CompoundFile(STORIES.read_bytes())
    with pytest.raises(NotAWordDocument):
        read_word(Stub(WordDocument=compound.read("WordDocument")))


def test_a_stream_that_is_not_a_word_document_is_refused():
    with pytest.raises(NotAWordDocument):
        read_word(Stub(WordDocument=b"\x00" * 600, **{"1Table": b""}))


# --- what is in the piece table and not on the page ------------------------
#
# A .doc keeps the text of a tracked deletion in the piece table beside the
# text that is printed, and so does a run marked hidden. Nothing about the
# characters says which is which: that is a `Chpx`, in a 512-byte page reached
# through `PlcfBteChpx`, and a reader that stops at the piece table reports a
# deleted sentence as though somebody could see it.


@pytest.fixture
def marks():
    return read_word(CompoundFile(MARKS.read_bytes()))


def test_deleted_text_is_not_reported_as_text_on_the_page(marks):
    visible = "".join(story.text for story in marks.stories)
    assert "disqualified for a late submission" not in visible


def test_deleted_text_comes_back_as_a_deletion_with_its_name_and_date(marks):
    deletions = [r for r in marks.revisions if r.kind == "deletion"]
    assert len(deletions) == 1
    assert deletions[0].text.strip() == (
        "The second bidder was disqualified for a late submission."
    )
    assert deletions[0].author == "Halina Probna-Test"
    assert deletions[0].date == "2019-04-02T11:14:00"


def test_an_insertion_is_on_the_page_and_stays_there(marks):
    """An insertion is text somebody added and everybody can read. Filtering
    it out with the deletions would take words off a page they are on."""
    visible = "".join(story.text for story in marks.stories)
    assert "Both bids were compliant." in visible
    assert [r.kind for r in marks.revisions if r.kind == "insertion"] == ["insertion"]


def test_hidden_text_is_not_reported_as_text_on_the_page(marks):
    visible = "".join(story.text for story in marks.stories)
    assert "reserve bidder is Wykonawca B" not in visible
    assert "Panel decision" in visible and "is final." in visible


def test_hidden_text_comes_back_as_something_the_report_can_state(marks):
    assert len(marks.hidden) == 1
    assert marks.hidden[0].text.strip() == "- reserve bidder is Wykonawca B -"


def test_hidden_text_is_the_finding_a_pdf_makes_for_the_same_thing():
    """Word's hidden attribute and a PDF render mode that paints nothing are
    one statement: the characters are in the file and not on the page. Same
    detector name, arriving from a different container."""
    from unmasker.detect import collect
    from unmasker.readers import read

    found = collect(read(MARKS))
    invisible = [f for f in found if f.detector == "invisible-text"]
    assert len(invisible) == 1
    assert "Wykonawca B" in invisible[0].machine_reads


def test_a_deletion_reaches_the_same_finding_a_docx_deletion_makes():
    from unmasker.detect import collect
    from unmasker.readers import read

    found = collect(read(MARKS))
    deleted = [f for f in found if f.detector == "deleted-text"]
    assert len(deleted) == 1
    assert "Halina Probna-Test" in deleted[0].summary


def test_a_document_with_no_marks_reports_none_rather_than_failing(stories):
    assert stories.revisions == ()
    assert stories.hidden == ()
    assert stories.properties_unread is False


def test_properties_that_cannot_be_read_are_not_passed_off_as_none():
    """The dangerous answer here is "no deletions". If the table that says
    which characters are deleted could not be read, nothing was searched, and
    the text must not be handed on as though it were all on the page."""
    compound = CompoundFile(MARKS.read_bytes())
    word = bytearray(compound.read("WordDocument"))
    # Point PlcfBteChpx past the end of the table stream it lives in.
    struct.pack_into("<II", word, 0x9A + 24 * 4, 1 << 30, 64)
    record = read_word(Stub(WordDocument=bytes(word), **{"1Table": compound.read("1Table")}))

    assert record.properties_unread is True
    assert any("could not be read" in remark for remark in record.remarks)


def test_a_file_whose_marks_are_unreadable_says_its_text_was_not_searched(tmp_path):
    from unmasker.readers import read

    compound = CompoundFile(MARKS.read_bytes())
    word = bytearray(compound.read("WordDocument"))
    struct.pack_into("<II", word, 0x9A + 24 * 4, 1 << 30, 64)
    broken = tmp_path / "broken.doc"
    broken.write_bytes(
        MARKS.read_bytes().replace(compound.read("WordDocument"), bytes(word))
    )
    assert read(broken).text_unread is True


# --- what the reader hands on -----------------------------------------------
#
# Reading the text is only half of it. Until this landed, a .doc carried
# `text_unread`, which told the metadata detector not to claim a gap it could
# not look for - and switched off twenty-odd detectors that need characters.
# The point of the format work is that they now run.


def test_a_doc_is_no_longer_a_file_whose_text_went_unread():
    from unmasker.readers import read

    got = read(STORIES)
    assert got.kind == "doc"
    assert got.text_unread is False
    assert got.has_text


def test_every_story_reaches_the_detectors_as_its_own_unit():
    from unmasker.readers import read

    got = read(STORIES)
    joined = "\n".join(unit.text for unit in got.units)
    assert "internal circulation only" in joined
    assert "figures not yet approved" in joined
    assert "the second bidder withdrew" in joined


def test_a_comment_arrives_as_the_finding_a_docx_comment_makes():
    from unmasker.detect import collect
    from unmasker.readers import read

    found = collect(read(STORIES))
    comments = [f for f in found if f.detector == "comment"]
    assert len(comments) == 1
    assert "Halina Probna-Test" in comments[0].summary
    assert "second bidder" in comments[0].machine_reads


def test_metadata_is_compared_against_the_text_now_there_is_text():
    """`undisclosed-metadata` was switched off for every .doc while the text
    went unread. A title the document never shows is exactly what it is for."""
    from unmasker.detect import collect
    from unmasker.readers import read

    found = collect(read(STORIES))
    undisclosed = [f for f in found if f.detector == "undisclosed-metadata"]
    assert any("Scoring pack - not for release" in f.machine_reads for f in undisclosed)


def test_a_field_instruction_is_reported_rather_than_quietly_dropped():
    from unmasker.readers import read

    got = read(STORIES)
    assert any("internal.example.invalid" in remark for remark in got.remarks)


def test_a_workbook_still_says_its_text_was_not_read():
    """BIFF is a different format and none of it is read. The remark that says
    so must not have been made general enough to cover a .doc as well."""
    from unmasker.readers import read

    got = read(Path(__file__).parent / "specimens" / "xls" / next(
        p.name for p in (Path(__file__).parent / "specimens" / "xls").glob("*.xls")
    ))
    assert got.text_unread is True
