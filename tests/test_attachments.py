"""Files carried inside files.

A PDF can hold whole other documents in `/Names/EmbeddedFiles`. They are on no
page, no viewer shows them unless asked, and printing the document does not
print them. The attachment travels with the file and appears nowhere in it,
which is the same statement every other detector here makes: the page and the
file do not agree about what is in this document.

This is not a redaction failure and must not be reported as one. An attachment
is a feature, used deliberately and constantly - an invoice with its XML, a
report with its data. The finding is that one is *there*, not that it is
sinister, and the basis is DIRECT because the bytes were read out.
"""

from pathlib import Path

from unmasker.detect import collect
from unmasker.findings import Basis
from unmasker.readers import read

SPECIMENS = Path(__file__).parent / "specimens" / "pdf"
CARRYING = SPECIMENS / "poppler-pdf-with-an-attachment.pdf"
BARE = SPECIMENS / "libreoffice-writer-metadata-leak.pdf"


def _findings(path: Path, detector: str):
    return [f for f in collect(read(path)) if f.detector == detector]


def test_an_attached_file_is_reported_with_the_name_it_travels_under():
    (found,) = _findings(CARRYING, "attached-file")
    assert "panel-note.txt" in found.summary
    assert found.basis is Basis.DIRECT


def test_an_attached_text_file_is_quoted_rather_than_only_counted():
    """A name and a byte count say a file is there. The point is what is in it."""
    (found,) = _findings(CARRYING, "attached-file")
    assert "240000" in found.machine_reads
    assert found.human_sees == ""


def test_the_page_that_carries_it_says_none_of_it():
    extraction = read(CARRYING)
    page_text = "\n".join(unit.text for unit in extraction.units)
    assert "240000" not in page_text
    assert "Kowalski" not in page_text


def test_a_pdf_with_no_attachment_is_not_reported():
    """The control. A detector that fires on every PDF is worse than none."""
    assert _findings(BARE, "attached-file") == []


# The office families say something different. An embedded object *is* on the
# page - what is on the page is a picture of it, written beside it for that
# purpose - while the package carries the file the picture was made from.

DOCX = Path(__file__).parent / "specimens" / "docx" / "libreoffice-writer-embedded-sheet.docx"
ODT = Path(__file__).parent / "specimens" / "odt" / "libreoffice-writer-embedded-sheet.odt"
PLAIN_DOCX = Path(__file__).parent / "specimens" / "docx" / "libreoffice-writer-metadata-leak.docx"


def test_a_word_document_carrying_a_workbook_reports_it():
    (found,) = _findings(DOCX, "attached-file")
    assert "oleObject1.xlsx" in found.summary
    assert found.basis is Basis.DIRECT


def test_the_summary_does_not_claim_an_embedded_object_is_off_the_page():
    """It is on the page. The picture is; the workbook behind it travels too,
    and saying otherwise would be the tool overstating its own finding."""
    (found,) = _findings(DOCX, "attached-file")
    assert "on no page" not in found.summary
    assert "rendering" in found.summary


def test_an_opendocument_embedded_object_is_reported_as_one_thing():
    """`Object 1/` is a sub-package of several members, and it is one object."""
    (found,) = _findings(ODT, "attached-file")
    assert "Object 1" in found.summary


def test_a_document_with_no_embedded_object_is_not_reported():
    assert _findings(PLAIN_DOCX, "attached-file") == []


# Descending into what is carried. A spreadsheet inside a document hides things
# exactly as a spreadsheet on disk does, and nothing was looking.


def test_a_hidden_sheet_inside_an_embedded_workbook_is_found():
    """The workbook behind the pictured table has a sheet marked hidden.

    Its values are in the document a person was sent. No page shows them, the
    picture does not show them, and the file this tool was pointed at is the
    one carrying them.
    """
    (found,) = _findings(DOCX, "hidden-sheet")
    assert "Workings" in found.summary
    assert "240000" in found.machine_reads


def test_a_finding_from_inside_says_which_object_it_came_from():
    """A hidden sheet in the document and one in a workbook it carries are not
    the same statement, and a reader must be able to tell them apart."""
    (found,) = _findings(DOCX, "hidden-sheet")
    assert "oleObject1.xlsx" in str(found.location)


def test_the_embedded_object_is_still_reported_in_its_own_right():
    """Reading inside it does not replace saying it is there."""
    assert len(_findings(DOCX, "attached-file")) == 1


def test_nothing_is_invented_for_a_document_carrying_nothing():
    assert _findings(PLAIN_DOCX, "hidden-sheet") == []


def test_json_says_which_object_a_finding_came_from_too():
    """The terminal report says `in oleObject1.xlsx`; --json said nothing.

    A pipeline reading the JSON could not tell a hidden sheet in the document
    from one in a workbook the document carries, which is the distinction the
    field was added for. The consumer that most needs it was the one not given
    it.
    """
    (found,) = _findings(DOCX, "hidden-sheet")
    assert found.as_dict()["location"]["inside"] == "oleObject1.xlsx"
