"""OpenDocument: the format `unmasker` used to refuse outright.

Until this existed the tool answered an .odt with "it looks like an
OpenDocument file, which unmasker does not read yet", which is a large refusal:
ODF is LibreOffice's native format and the one a great deal of European
government and legal work is written in.

The care this format needs, and OOXML does not, is that **the two things which
must not be read as body text live inside the body**. `<text:tracked-changes>`
sits at the top of `office:text` and holds every deleted passage;
`<office:annotation>` sits inline in its paragraph and holds a comment.
Extracting the body naively reports both as ordinary visible prose - exactly
backwards, since a reader of the page sees neither.
"""

import zipfile

import pytest
from conftest import SPECIMENS

from unmasker.findings import Basis
from unmasker.metadata import read_odf as read_odf_metadata
from unmasker.odf.revisions import read_revisions
from unmasker.readers import UnreadableFile, read
from unmasker.revisions import detect

SPECIMEN = SPECIMENS / "odf" / "libreoffice-writer-position-note.odt"

DELETED = "the earlier estimate of 3.1 million"
COMMENT = "Do not share the working file with the other side."
VISIBLE = "The figure is withheld pending advice."


def record():
    with zipfile.ZipFile(SPECIMEN) as archive:
        return read_revisions(archive)


def meta():
    with zipfile.ZipFile(SPECIMEN) as archive:
        return read_odf_metadata(archive)


# --------------------------------------------------------------------------
# the file is accepted at all
# --------------------------------------------------------------------------


def test_an_odt_is_read_rather_than_refused():
    got = read(SPECIMEN)
    assert got.kind == "odf"
    assert got.has_text


def test_the_container_decides_and_not_the_extension(tmp_path):
    """A forensic tool has no business trusting a filename."""
    disguised = tmp_path / "note.docx"
    disguised.write_bytes(SPECIMEN.read_bytes())
    assert read(disguised).kind == "odf"


def test_a_zip_that_is_neither_is_still_refused(tmp_path):
    import io

    path = tmp_path / "plain.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "not a document")
    path.write_bytes(buffer.getvalue())
    with pytest.raises(UnreadableFile):
        read(path)


# --------------------------------------------------------------------------
# what must not appear in the body text
# --------------------------------------------------------------------------


def test_the_body_text_is_what_a_reader_sees():
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert VISIBLE in body


def test_the_deleted_passage_is_not_read_as_body_text():
    """It lives inside `office:text`, at the top. Reading it as prose would
    report the struck-out sentence as something on the page."""
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert DELETED not in body


def test_the_comment_is_not_read_as_body_text():
    """It sits inline in the paragraph it belongs to."""
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert COMMENT not in body


def test_the_text_that_followed_the_comment_is_kept():
    """The comment sits mid-sentence on purpose. Skipping a subtree must not
    swallow what comes after it on the line, and a comment at the end of a
    paragraph would never test that."""
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert "The panel meets again in June." in body


def test_the_header_is_read_from_styles_xml():
    """ODF keeps a master page's header in a different part of the zip. A
    document reported as holding nothing because only `content.xml` was read
    has been told something untrue."""
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert "POSITION NOTE - DRAFT" in body


def test_the_inserted_text_is_on_the_page_and_is_not_hidden():
    """`a figure to be settled` replaced the struck-out figure. It is in the
    document a reader prints, so it is body text and not a finding."""
    body = "\n".join(u.text for u in read(SPECIMEN).units)
    assert "a figure to be settled" in body
    reads = " ".join(f.machine_reads for f in detect(record()))
    assert "a figure to be settled" not in reads


def test_the_insertion_is_still_counted_in_the_history():
    """It hides no words, but it does say somebody was here and when."""
    kinds = [r.kind for r in record().revisions]
    assert sorted(kinds) == ["deletion", "insertion"]
    (history,) = [f for f in detect(record()) if f.detector == "revision-history"]
    assert "insertion" in history.summary


# --------------------------------------------------------------------------
# what is reported
# --------------------------------------------------------------------------


def test_the_deletion_is_reported_with_its_author():
    (found,) = [f for f in detect(record()) if f.detector == "deleted-text"]
    assert found.machine_reads == DELETED
    assert "Halina Probna-Test" in found.summary
    assert "2024-05-06" in found.summary


def test_the_comment_is_reported():
    (found,) = [f for f in detect(record()) if f.detector == "comment"]
    assert found.machine_reads == COMMENT


def test_the_change_info_is_not_part_of_the_deleted_text():
    """`office:change-info` is metadata about the region, not its content.
    Reading it in would put the author's name inside the deleted sentence."""
    (deletion,) = [r for r in record().revisions if r.kind == "deletion"]
    assert deletion.text == DELETED
    assert "Halina" not in deletion.text


def test_the_history_is_one_finding_here_too():
    found = [f for f in detect(record()) if f.detector == "revision-history"]
    assert len(found) == 1
    assert found[0].basis is Basis.SELF_REPORTED


def test_the_authorship_caveat_does_not_name_word_on_an_odf_file():
    """It used to say `whatever the copy of Word was configured to say`, which
    is not true of a file LibreOffice wrote in its own format."""
    (found,) = [f for f in detect(record()) if f.detector == "revision-history"]
    assert "Word" not in found.summary


# --------------------------------------------------------------------------
# metadata
# --------------------------------------------------------------------------


def test_meta_xml_is_read():
    fields = {f.name: f for f in meta().fields}
    assert fields["initial-creator"].value == "Halina Probna-Test"
    assert fields["title"].value == "Position note - internal only"


def test_the_odf_generator_is_a_tool_field():
    """`meta:generator` is `LibreOffice/24.2.7.2$Linux_X86_64` - the same string
    and the same dotted quad as `docProps/app.xml`, and the same answer."""
    generator = meta().get("generator")
    assert "24.2.7.2" in generator.value
    assert generator.role == "tool"


def test_the_editing_cycles_are_a_count_and_not_a_finding():
    assert meta().get("editing-cycles").role == "count"


def test_a_user_defined_property_is_content_whatever_it_is_called():
    """ODF's custom property, and the same rule OOXML's gets: a standard
    property is something a tool wrote, a custom one is something a person put
    there on purpose, and no name table anticipates them."""
    client = meta().get("Client")
    assert client.value == "Meridian Trust BV"
    assert client.role == "content"


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


def test_one_odt_produces_five_kinds_of_finding():
    """A tracked deletion, a comment, the revision history, two metadata
    values and a zero-width space, from one file."""
    from unmasker.cli import collect

    kinds = {f.detector for f in collect(read(SPECIMEN))}
    assert kinds == {
        "deleted-text",
        "comment",
        "revision-history",
        "undisclosed-metadata",
        "zero-width",
    }
    reads = {f.machine_reads for f in collect(read(SPECIMEN))}
    assert "Meridian Trust BV" in reads


def test_the_zero_width_space_in_the_address_is_found():
    from unmasker.cli import collect

    found = [f for f in collect(read(SPECIMEN)) if f.detector == "zero-width"]
    assert found and "h.probna" in found[0].human_sees
