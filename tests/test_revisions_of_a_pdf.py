"""What an earlier revision of a PDF still holds.

A PDF is appended to rather than rewritten. Editing one leaves the original
bytes where they were and writes a new cross-reference section after them, so
every earlier revision of the document is still in the file. Delete a page and
the page does not go anywhere: the new catalogue stops pointing at it, every
viewer stops showing it, and the text is still there.

This is the cleanest failed redaction there is - nothing was covered, nothing
was made invisible, the content was simply unreferenced - and it is invisible
to any tool that reads only what the current catalogue points at.

The revision boundaries are read out of the raw bytes rather than asked of the
parser, because the specimen's second revision is written by that same parser
and a reader agreeing with its own writer proves less than nothing.
"""

from pathlib import Path

from unmasker.detect import collect
from unmasker.findings import Basis
from unmasker.readers import read

SPECIMENS = Path(__file__).parent / "specimens" / "pdf"
UPDATED = SPECIMENS / "pypdf-incremental-page-removed.pdf"
SINGLE = SPECIMENS / "libreoffice-writer-metadata-leak.pdf"


def _findings(path: Path, detector: str):
    return [f for f in collect(read(path)) if f.detector == detector]


def test_a_page_removed_by_an_incremental_update_is_still_reported():
    (found,) = _findings(UPDATED, "earlier-revision")
    assert found.basis is Basis.DIRECT


def test_what_the_earlier_revision_held_is_quoted():
    """A count of revisions is trivia. What was on the deleted page is not."""
    (found,) = _findings(UPDATED, "earlier-revision")
    assert "240000" in found.machine_reads
    assert "ANNEX" in found.machine_reads


def test_the_current_document_shows_none_of_it():
    extraction = read(UPDATED)
    shown = "\n".join(unit.text for unit in extraction.units)
    assert "240000" not in shown
    assert "ANNEX" not in shown


def test_the_summary_says_how_many_revisions_there_are():
    (found,) = _findings(UPDATED, "earlier-revision")
    assert "2" in found.summary


def test_a_pdf_written_once_is_not_reported():
    """The control. Most PDFs have exactly one revision and must stay silent."""
    assert _findings(SINGLE, "earlier-revision") == []
