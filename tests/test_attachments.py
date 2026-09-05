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
