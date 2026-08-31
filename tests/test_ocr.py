"""Reading the page back, and comparing it with what the file says.

`HANDOFF.md` decision 4 deferred this and recorded why: it needs an OCR engine
and a renderer, two heavy external binaries, and that breaks *point it at a
file, get an answer*. The reason still holds, so this is off unless asked for.
What has changed is that the rest stands, which is the condition the decision
set for coming back to it.

## Why it is worth the binaries

Every other detector here knows a trick. `covered_text` knows about filled
paths, `invisible_text` about render modes and opacity, `low_contrast_text`
about colour. Each was written after a producer was caught doing something
particular, and each would miss the next thing a producer invents.

This one knows nothing. It renders the page, reads the picture back, and asks
whether the words in the file are on it. A redaction technique nobody here has
thought of still fails that question.

## Why it can never be `DIRECT`

OCR is wrong constantly, and its being wrong looks exactly like concealment.
On `libreoffice-writer-properly-redacted.pdf` tesseract reads `Name:` as `TT`
and `Address:` as `ee`, because a black bar abutting a label defeats its
segmentation - three words that are plainly on the page, reported missing.

Which is why the threshold below exists, and why it is three. Measured across
the specimens: the control's longest run of consecutive unread words is **2**,
and every file that hides something has a run of **5 or more**. A single
missing word is an OCR failure far more often than it is a concealment; five in
a row is something covering them.
"""

import shutil

import pytest
from conftest import SPECIMENS, page_of

from unmasker.pdf.detectors import unextractable_text, unrendered_text
from unmasker.pdf.interpreter import interpret_page
from unmasker.pdf.rendered import UNREAD_RUN, read_page_back, tools_available

pytestmark = pytest.mark.skipif(
    not (shutil.which("gs") and shutil.which("tesseract")),
    reason="needs ghostscript and tesseract",
)

_CACHE: dict = {}


def read_back(name: str):
    """One render-and-OCR per specimen for the whole module; it is seconds."""
    if name not in _CACHE:
        page = interpret_page(page_of(name))
        _CACHE[name] = (page, read_page_back(SPECIMENS / "pdf" / name, 1, page.box))
    return _CACHE[name]


def unrendered(name: str):
    page, (words, _) = read_back(name)
    return unrendered_text(page, words)


def reads(findings):
    return " | ".join(f.machine_reads for f in findings)


# --------------------------------------------------------------------------
# the mechanism-independent catch
# --------------------------------------------------------------------------


def test_a_black_bar_is_found_without_knowing_anything_about_rectangles():
    """The same finding `covered_text` makes, arrived at from the picture."""
    found = unrendered("libreoffice-writer-black-bars.pdf")
    assert "Wanda Testowa-Przyklad" in reads(found)
    assert "ul. Przykladowa" in reads(found)


def test_transparent_text_is_found_the_same_way():
    found = unrendered("chrome-transparent-text.pdf")
    assert "reserve price" in reads(found) or "one tenth opacity" in reads(found)


def test_text_hidden_by_colour_and_by_position_is_found_the_same_way():
    found = unrendered("libreoffice-writer-hidden-in-plain-sight.pdf")
    assert "simply white" in reads(found)
    assert "crop box" in reads(found)


def test_every_finding_is_circumstantial():
    """OCR being wrong looks exactly like concealment, and it is wrong often."""
    from unmasker.findings import Basis

    for name in (
        "libreoffice-writer-black-bars.pdf",
        "chrome-transparent-text.pdf",
    ):
        assert all(f.basis is Basis.CIRCUMSTANTIAL for f in unrendered(name))


def test_the_summary_says_ocr_may_simply_have_failed():
    (found, *_) = unrendered("libreoffice-writer-black-bars.pdf")
    assert "OCR" in found.summary or "read back" in found.summary


# --------------------------------------------------------------------------
# the control, and the threshold that keeps it quiet
# --------------------------------------------------------------------------


def test_the_properly_redacted_control_stays_silent():
    """Its longest run of unread words is two - the labels beside the bars,
    which tesseract reads as `TT` and `ee`. Those are the engine's mistakes,
    not the document's."""
    assert unrendered("libreoffice-writer-properly-redacted.pdf") == []


def test_two_clean_pages_stay_silent():
    for name in ("libreoffice-writer-metadata-leak.pdf", "text-on-an-image.pdf"):
        assert unrendered(name) == [], name


def test_the_threshold_is_three_and_the_control_is_why():
    """Recorded rather than tuned quietly: the control's longest run is 2 and
    every hiding specimen's is 5 or more, so the line falls between them."""
    assert UNREAD_RUN == 3


# --------------------------------------------------------------------------
# the other direction
# --------------------------------------------------------------------------


def test_a_page_with_no_text_layer_can_finally_be_read():
    """The question this tool has declined to answer since task 1. The page
    shows words; the file holds none of them."""
    page, (words, _) = read_back("flattened-to-image.pdf")
    (found,) = unextractable_text(page, words)
    assert "SYNTHETIC" in found.human_sees.upper()


def test_that_findings_columns_are_the_right_way_round():
    """Every other detector fills `machine reads` and leaves `human sees`
    empty. This one is the only gap that runs the other way: a person can read
    the page and no parser can, so the columns swap - and what goes in the
    human column is this tool's reading of a picture rather than anything the
    file states."""
    page, (words, _) = read_back("flattened-to-image.pdf")
    (found,) = unextractable_text(page, words)
    assert found.human_sees.strip()
    assert found.machine_reads == ""
    assert "reading of the picture" in found.summary


def test_an_invisible_ocr_layer_is_still_text_in_the_file():
    """The scanned specimen's words are in the file, in render mode 3, and
    `pdftotext` reads them straight out. Reporting `the page shows them and no
    parser gets them` would be a false statement about a file this project can
    itself read."""
    page, (words, _) = read_back("redacted-scan-with-ocr.pdf")
    assert unextractable_text(page, words) == []


def test_a_page_whose_text_is_all_in_the_file_reports_nothing_that_way():
    page, (words, _) = read_back("libreoffice-writer-metadata-leak.pdf")
    assert unextractable_text(page, words) == []


# --------------------------------------------------------------------------
# the binaries
# --------------------------------------------------------------------------


def test_a_low_confidence_reading_is_not_claimed_as_text_on_the_page():
    """Tesseract reports a confidence per word and finds words in noise. Saying
    the page shows something the file lacks, on the strength of a guess the
    engine itself does not believe, would be inventing the evidence."""
    from unmasker.pdf.geometry import Rect
    from unmasker.pdf.interpreter import InterpretedPage
    from unmasker.pdf.rendered import ReadWord

    page = InterpretedPage(number=1, box=Rect(0, 0, 595, 842))
    guesses = [
        ReadWord(text=f"noise{i}", bbox=Rect(10 + i * 30, 700, 35 + i * 30, 712), confidence=11.0)
        for i in range(6)
    ]
    assert unextractable_text(page, guesses) == []

    confident = [
        ReadWord(text=f"word{i}", bbox=Rect(10 + i * 30, 700, 35 + i * 30, 712), confidence=95.0)
        for i in range(6)
    ]
    assert unextractable_text(page, confident)


def test_the_tools_are_named_when_they_are_missing():
    present, missing = tools_available({"gs": None, "tesseract": None})
    assert not present
    assert "gs" in missing and "tesseract" in missing


def test_a_missing_binary_is_a_remark_and_not_a_crash(tmp_path):
    """A forensic tool that dies because an optional dependency is absent has
    made the dependency compulsory."""
    words, remarks = read_page_back(
        SPECIMENS / "pdf" / "libreoffice-writer-black-bars.pdf",
        1,
        interpret_page(page_of("libreoffice-writer-black-bars.pdf")).box,
        renderer="definitely-not-a-program",
    )
    assert words == []
    (remark,) = remarks
    assert "definitely-not-a-program" in remark
    # Checked before running rather than after failing, so the remark can say
    # what is wrong instead of quoting an errno at somebody.
    assert "not on PATH" in remark
    assert "OCR engine" in remark
