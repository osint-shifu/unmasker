"""Presentations, in both families.

A deck hides two things no other container has.

A **slide marked hidden** is skipped when the deck is shown and travels with
the file exactly as it was authored. A **speaker note** was never on the screen
at all - which is why people write candid things in them, and why the candid
thing goes out with the file.

Both are the statement this tool makes everywhere: in the file, not on the
thing anybody looked at.

## Why this arrived last

`unmasker` refused decks outright for most of its life, and said so rather than
half-reading them. Reading a deck as a text document would have reported a
hidden slide and a speaker note as visible prose and then called the file
clean - the same defect the spreadsheet reader was written to remove.

The reader could not be written honestly because `libreoffice-impress` was not
installed, so no producer on this machine could write a deck, and
`CONTRIBUTING.md` is explicit that a detector proved only against a hand-built
fixture is the shape of the bug that started this project. Installing Impress
is the whole of what unblocked it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unmasker.cli import collect
from unmasker.readers import read
from unmasker.slides import SlideRecord, detect

SPECIMENS = Path(__file__).parent / "specimens"

ODP = SPECIMENS / "odp" / "libreoffice-impress-hidden-slide.odp"
PPTX = SPECIMENS / "pptx" / "libreoffice-impress-hidden-slide.pptx"

BOTH = pytest.mark.parametrize("specimen", [ODP, PPTX], ids=["odp", "pptx"])

CUT = "Redundancies"
CUT_BODY = "41 roles"
NOTE = "Do not give the headcount number"
SHOWN = "Q3 board review"


def findings_for(specimen: Path):
    return collect(read(specimen))


def by_detector(specimen: Path, name: str):
    return [f for f in findings_for(specimen) if f.detector == name]


# --------------------------------------------------------------------------
# it is read at all, and read as a presentation
# --------------------------------------------------------------------------


@BOTH
def test_a_deck_is_no_longer_refused(specimen):
    assert read(specimen).kind == "presentation"


@BOTH
def test_the_visible_slides_are_read_as_text(specimen):
    """The character detectors search whatever a reader yields, so what is on
    the screen has to arrive as text."""
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert SHOWN in shown
    assert "Outlook" in shown


@BOTH
def test_nothing_hidden_reaches_the_visible_text(specimen):
    """The defect the refusal existed to prevent. A hidden slide read as body
    text is concealed content handed to the detectors as though somebody had
    seen it - and then reported clean."""
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert CUT not in shown
    assert CUT_BODY not in shown
    assert NOTE not in shown


# --------------------------------------------------------------------------
# the hidden slide
# --------------------------------------------------------------------------


@BOTH
def test_the_hidden_slide_is_reported_once(specimen):
    (found,) = by_detector(specimen, "hidden-slide")
    assert "2" in found.summary, "the summary should say which slide it was"


@BOTH
def test_the_hidden_slide_quotes_what_is_on_it(specimen):
    (found,) = by_detector(specimen, "hidden-slide")
    assert CUT in found.machine_reads
    assert CUT_BODY in found.machine_reads


@BOTH
def test_the_visible_slides_are_not_reported_as_hidden(specimen):
    (found,) = by_detector(specimen, "hidden-slide")
    assert SHOWN not in found.machine_reads
    assert "Outlook" not in found.machine_reads


# --------------------------------------------------------------------------
# the speaker note
# --------------------------------------------------------------------------


@BOTH
def test_the_speaker_note_is_reported(specimen):
    (found,) = by_detector(specimen, "speaker-notes")
    assert NOTE in found.machine_reads


@BOTH
def test_the_note_says_which_slide_it_belongs_to(specimen):
    """A note without its slide sends a reader through the whole deck looking
    for it."""
    (found,) = by_detector(specimen, "speaker-notes")
    assert "1" in found.summary


@BOTH
def test_a_slide_without_notes_produces_no_note_finding(specimen):
    """Two of the three slides carry none. A finding per slide regardless
    would be a report mostly made of nothing."""
    assert len(by_detector(specimen, "speaker-notes")) == 1


# --------------------------------------------------------------------------
# both families, one document
# --------------------------------------------------------------------------


@BOTH
def test_both_families_report_the_same_hiding(specimen):
    """One source deck exported twice. ODF puts a slide's visibility behind a
    named style and OOXML writes `show="0"` on the slide itself; a reader that
    got either wrong would disagree with the other."""
    kinds = {f.detector for f in findings_for(specimen)}
    assert {"hidden-slide", "speaker-notes"} <= kinds


@BOTH
def test_a_deck_that_hides_something_does_not_exit_clean(specimen):
    assert findings_for(specimen)


# --------------------------------------------------------------------------
# the record, and what mutation testing asked for
# --------------------------------------------------------------------------


def test_a_record_with_nothing_hidden_produces_no_findings():
    assert detect(SlideRecord()) == []


def test_a_hidden_slide_with_nothing_on_it_is_not_reported():
    """A finding that quotes nothing teaches a reader to skip findings."""
    from unmasker.slides import Slide

    record = SlideRecord(slides=(Slide(number=1, hidden=True, text=""),))
    assert detect(record) == []


def test_an_empty_note_is_not_reported():
    from unmasker.slides import Slide

    record = SlideRecord(slides=(Slide(number=1, text="on screen", notes="   "),))
    assert detect(record) == []


def test_a_hidden_slide_does_not_also_report_its_notes():
    """The slide is already the finding. Saying its notes are also unseen tells
    a reader nothing they did not just read."""
    from unmasker.slides import Slide

    record = SlideRecord(slides=(Slide(number=2, hidden=True, text="cut", notes="also cut"),))
    assert [f.detector for f in detect(record)] == ["hidden-slide"]


# --------------------------------------------------------------------------
# what mutation testing asked for
#
# Four claims the specimen cannot discriminate, because LibreOffice never
# writes the shapes that would tell them apart. Each is held here instead, and
# each is a producer behaviour Excel or PowerPoint would produce.
# --------------------------------------------------------------------------

import io  # noqa: E402
import zipfile  # noqa: E402

from unmasker.ooxml.slides import read_slides as read_pptx_slides  # noqa: E402

REL = '<Relationship Id="{rid}" Target="{target}"/>'


def deck(slides: dict[str, str], notes: dict[str, str] | None = None) -> zipfile.ZipFile:
    """A .pptx assembled from parts, so a slide can carry what LibreOffice
    would never write on one."""
    notes = notes or {}
    buffer = io.BytesIO()
    ns = (
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    )
    with zipfile.ZipFile(buffer, "w") as z:
        ids = "".join(
            f'<p:sldId id="{256 + i}" r:id="rId{i + 1}"/>' for i in range(len(slides))
        )
        z.writestr(
            "ppt/presentation.xml",
            f"<p:presentation {ns}><p:sldIdLst>{ids}</p:sldIdLst></p:presentation>",
        )
        z.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                REL.format(rid=f"rId{i + 1}", target=f"slides/{name}")
                for i, name in enumerate(slides)
            )
            + "</Relationships>",
        )
        for name, body in slides.items():
            z.writestr(f"ppt/slides/{name}", body.replace("{ns}", ns))
            if name in notes:
                note_part = name.replace("slide", "notesSlide")
                z.writestr(f"ppt/notesSlides/{note_part}", notes[name].replace("{ns}", ns))
                z.writestr(
                    f"ppt/slides/_rels/{name}.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + REL.format(rid="rId1", target=f"../notesSlides/{note_part}")
                    + "</Relationships>",
                )
    return zipfile.ZipFile(buffer)


def slide_xml(text: str, show: str | None = None) -> str:
    attr = f' show="{show}"' if show is not None else ""
    return (
        f"<p:sld {{ns}}{attr}><p:cSld><p:spTree><p:sp><p:txBody>"
        f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )


def test_show_is_read_for_what_it_says_not_whether_it_is_there():
    """The producer fact this reader was built around, and the specimen cannot
    test it: LibreOffice omits `show` on a visible slide, so a reader that
    checked for the attribute's presence agrees with one that reads it.

    PowerPoint writes `show="1"`, and there the two disagree completely.
    """
    record = read_pptx_slides(
        deck(
            {
                "slide1.xml": slide_xml("shown out loud", show="1"),
                "slide2.xml": slide_xml("cut", show="0"),
            }
        )
    )
    assert [s.hidden for s in record.slides] == [False, True]


def test_slide_order_comes_from_the_deck_not_the_part_names():
    """`slide10.xml` sorts before `slide2.xml`. A deck reported with its slides
    renumbered sends a reader to the wrong one, which is worse than not
    numbering them."""
    record = read_pptx_slides(
        deck(
            # Declared in deck order. Sorted by part name they would come out
            # slide1, slide10, slide2 - so the two orders disagree, which is
            # the whole point. An earlier version listed them in an order where
            # both agreed, and proved nothing.
            {
                "slide1.xml": slide_xml("first"),
                "slide2.xml": slide_xml("second"),
                "slide10.xml": slide_xml("third"),
            }
        )
    )
    assert [s.text for s in record.slides] == ["first", "second", "third"]
    assert [s.number for s in record.slides] == [1, 2, 3]


def test_a_notes_slide_does_not_quote_the_slide_back():
    """PresentationML puts a copy of the slide's own text into a placeholder on
    the notes slide. Reading every `a:t` in the part quotes the slide as though
    the speaker had written it."""
    notes = (
        "<p:notes {ns}><p:cSld><p:spTree>"
        # `title`, not `sldImg`: the slide *image* placeholder holds a picture,
        # and putting the text copy there made the filter under test moot.
        '<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
        "<p:txBody><a:p><a:r><a:t>Q3 board review</a:t></a:r></a:p></p:txBody></p:sp>"
        '<p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>'
        "<p:txBody><a:p><a:r><a:t>do not say the number</a:t></a:r></a:p></p:txBody></p:sp>"
        "</p:spTree></p:cSld></p:notes>"
    )
    record = read_pptx_slides(
        deck({"slide1.xml": slide_xml("Q3 board review")}, notes={"slide1.xml": notes})
    )
    (slide,) = record.slides
    assert slide.notes == "do not say the number"
    assert "Q3 board review" not in slide.notes


def test_a_hidden_slide_quotes_its_notes_along_with_it():
    """A note on a hidden slide is hidden twice over, and is reported once -
    inside the slide's finding rather than as a second one. No producer here
    writes a deck with both, so nothing else holds this."""
    from unmasker.slides import Slide

    record = SlideRecord(
        slides=(Slide(number=2, hidden=True, text="cut slide", notes="and the note on it"),)
    )
    (found,) = detect(record)
    assert "cut slide" in found.machine_reads
    assert "and the note on it" in found.machine_reads
