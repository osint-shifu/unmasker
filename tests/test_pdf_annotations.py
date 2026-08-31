"""Annotations: what hangs off a page without being on it.

A comment in a PDF is a dictionary attached to the page, with the text in
`/Contents` and the author in `/T`. It is not part of the page. It does not
print, `pdftotext` does not report it, and a reader looking at the document
never meets it - and every PDF library reads it in one line.

The interpreter read `/Contents` on the *page* and never looked at `/Annots` at
all, so this was a blind spot rather than a gap in the specimens: no amount of
content-stream work would ever have found it.

`/FreeText` is the exception and is deliberately not reported. Its contents are
*drawn* on the page, so there is no gap between what a reader sees and what a
parser gets - which is the only thing this tool has to say about anything.
"""

import pytest
from conftest import SPECIMENS, page_of
from pypdf import PdfReader

from unmasker.pdf.annotations import Annotation, read_annotations
from unmasker.pdf.detectors import annotation_text
from unmasker.pdf.interpreter import interpret_page

SPECIMEN = "libreoffice-writer-pdf-comments.pdf"


class StubPage(dict):
    def get_object(self):
        return self


def page_with(*annots) -> StubPage:
    """A page whose /Annots holds whatever is given, including things that are
    not dictionaries - which is what a damaged file holds."""
    return StubPage({"/Annots": [StubPage(a) if isinstance(a, dict) else a for a in annots]})


# --------------------------------------------------------------------------
# reading them
# --------------------------------------------------------------------------


def test_both_comments_of_the_specimen_are_read():
    found = read_annotations(page_of(SPECIMEN))
    comments = [a for a in found if a.contents]
    assert len(comments) == 2
    assert any("Do not minute this" in a.contents for a in comments)
    assert any("has to be disclosed" in a.contents for a in comments)


def test_the_author_comes_back_with_the_comment():
    found = read_annotations(page_of(SPECIMEN))
    first = next(a for a in found if "Do not minute" in (a.contents or ""))
    assert "Anna Testowa" in first.author


def test_a_popup_carries_no_text_of_its_own():
    """LibreOffice writes a /Popup beside each /Text. It is the window the
    comment appears in, not the comment."""
    found = read_annotations(page_of(SPECIMEN))
    assert any(a.subtype == "Popup" for a in found)
    assert all(not a.contents for a in found if a.subtype == "Popup")


def test_a_page_with_no_annotations_reads_as_none():
    assert read_annotations(page_of("libreoffice-writer-black-bars.pdf")) == []


def test_a_malformed_annotation_does_not_lose_the_others():
    page = page_with(
        {"/Subtype": "/Text", "/Contents": "kept"},
        "not a dictionary at all",
        {"/Subtype": "/Text", "/Contents": "also kept"},
    )
    found = read_annotations(page)
    assert [a.contents for a in found if a.contents] == ["kept", "also kept"]


# --------------------------------------------------------------------------
# reporting them
# --------------------------------------------------------------------------


def test_a_comment_becomes_a_finding():
    interpreted = interpret_page(page_of(SPECIMEN))
    found = annotation_text(interpreted)
    assert len(found) == 2
    assert all(f.detector == "comment" for f in found)
    assert all(f.human_sees == "" for f in found)


def test_the_finding_names_the_author_and_the_kind():
    interpreted = interpret_page(page_of(SPECIMEN))
    first = next(f for f in annotation_text(interpreted) if "Do not minute" in f.machine_reads)
    assert "Anna Testowa" in first.summary
    assert "Text" in first.summary or "note" in first.summary


def test_the_visible_text_of_that_specimen_is_not_reported():
    interpreted = interpret_page(page_of(SPECIMEN))
    reads = " ".join(f.machine_reads for f in annotation_text(interpreted))
    assert "board approved" not in reads.lower()


def test_free_text_annotations_are_not_reported():
    """A /FreeText annotation draws its contents on the page. There is no gap
    between what a reader sees and what a parser gets, which is the only thing
    this tool has to say about anything."""
    page = page_with({"/Subtype": "/FreeText", "/Contents": "printed on the page"})
    assert [a.contents for a in read_annotations(page)] == ["printed on the page"]
    from unmasker.pdf.geometry import Rect
    from unmasker.pdf.interpreter import InterpretedPage

    interpreted = InterpretedPage(
        number=1, box=Rect(0, 0, 595, 842), annotations=tuple(read_annotations(page))
    )
    assert annotation_text(interpreted) == []


@pytest.mark.parametrize("subtype", ["Text", "Highlight", "StrikeOut", "Square", "Stamp"])
def test_the_subtypes_that_carry_a_note_rather_than_page_text(subtype):
    from unmasker.pdf.geometry import Rect
    from unmasker.pdf.interpreter import InterpretedPage

    interpreted = InterpretedPage(
        number=1,
        box=Rect(0, 0, 595, 842),
        annotations=(Annotation(subtype=subtype, contents="a private note"),),
    )
    (found,) = annotation_text(interpreted)
    assert found.machine_reads == "a private note"


def test_an_empty_comment_is_not_a_finding():
    from unmasker.pdf.geometry import Rect
    from unmasker.pdf.interpreter import InterpretedPage

    interpreted = InterpretedPage(
        number=1,
        box=Rect(0, 0, 595, 842),
        annotations=(Annotation(subtype="Text", contents="   "),),
    )
    assert annotation_text(interpreted) == []


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


def test_pdftotext_does_not_report_these_and_unmasker_does():
    """The whole point. A reader checking the obvious way finds nothing."""
    import subprocess

    path = SPECIMENS / "pdf" / SPECIMEN
    extracted = subprocess.run(
        ["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=60
    ).stdout
    assert "Do not minute this" not in extracted

    found = annotation_text(interpret_page(PdfReader(str(path)).pages[0]))
    assert any("Do not minute this" in f.machine_reads for f in found)
