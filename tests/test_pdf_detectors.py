"""Text under a filled shape, and text that is never painted at all.

The unit tests build an `InterpretedPage` by hand, because the questions they
ask - does z-order matter, does alpha, does a partial overlap report partially -
are about the detector and not about any PDF. The integration tests run on the
committed specimens, which is where a detector meets what producers actually do.

Two negatives carry as much weight as the positives. The properly-redacted
control has the same four bars at the same coordinates as the failed specimen
and must produce nothing; the values under those bars were removed, and a tool
that cannot tell the two apart has not established anything about either.
"""

import pytest
from conftest import page_of

from unmasker.findings import Basis
from unmasker.pdf.detectors import (
    _angle_of,
    _lines,
    covered_text,
    invisible_text,
    low_contrast_text,
    off_page_text,
    remarks,
    text_under_image,
)
from unmasker.pdf.geometry import BLACK, WHITE, Colour, Rect
from unmasker.pdf.interpreter import Glyph, InterpretedPage, Shape, TextRun, interpret_page

PAGE = Rect(0, 0, 595, 842)


def glyphs(text: str, x: float = 100, y: float = 200, width: float = 10) -> tuple:
    """A horizontal run's glyphs, with the origin the line grouping keys on.

    Setting `origin` matters: it defaults to (0, 0), so a fixture that left it
    alone would put every glyph on one line and quietly stop testing the
    grouping at all.
    """
    return tuple(
        Glyph(
            char=ch,
            code=ord(ch),
            bbox=Rect(x + i * width, y, x + (i + 1) * width, y + 10),
            origin=(x + i * width, y),
        )
        for i, ch in enumerate(text)
    )


def run(text: str, *, order: int = 0, mode: int = 0, fill=BLACK, stroke=None, **kw) -> TextRun:
    gs = glyphs(text, **kw)
    return TextRun(
        text=text,
        glyphs=gs,
        bbox=Rect(gs[0].bbox.x0, gs[0].bbox.y0, gs[-1].bbox.x1, gs[-1].bbox.y1),
        font="F1",
        size=10,
        render_mode=mode,
        fill=fill,
        stroke=stroke,
        order=order,
    )


def bar(x0, y0, x1, y1, *, order: int = 1, colour=BLACK, alpha: float = 1.0, clip=None) -> Shape:
    box = Rect(x0, y0, x1, y1)
    return Shape(
        kind="fill",
        operator="f",
        points=((x0, y0), (x1, y1)),
        bbox=box,
        colour=colour,
        clip=clip or PAGE,
        alpha=alpha,
        order=order,
    )


def image(x0, y0, x1, y1, *, order: int = 1) -> Shape:
    return Shape(
        kind="image",
        operator="Do",
        points=((x0, y0), (x1, y1)),
        bbox=Rect(x0, y0, x1, y1),
        colour=None,
        clip=PAGE,
        order=order,
    )


def page(*items) -> InterpretedPage:
    return InterpretedPage(
        number=1,
        box=PAGE,
        shapes=tuple(i for i in items if isinstance(i, Shape)),
        texts=tuple(i for i in items if isinstance(i, TextRun)),
    )


# --------------------------------------------------------------------------
# the basic finding
# --------------------------------------------------------------------------


def test_text_under_a_later_filled_shape_is_reported():
    (found,) = covered_text(page(run("SECRET", order=0), bar(95, 195, 300, 215, order=1)))
    assert found.detector == "covered-text"
    assert found.basis is Basis.DIRECT
    assert found.machine_reads == "SECRET"
    assert found.location.page == 1


def test_what_a_human_sees_is_a_bar_not_the_text():
    (found,) = covered_text(page(run("SECRET", order=0), bar(95, 195, 300, 215, order=1)))
    assert set(found.human_sees) == {"█"}
    assert len(found.human_sees) == len("SECRET")


def test_a_light_shape_is_drawn_differently_from_a_dark_one():
    """White-on-white hides text just as well, and a reader looking at the page
    sees nothing at all rather than a bar. Saying `████` there would describe a
    page that does not exist."""
    (found,) = covered_text(
        page(run("SECRET", order=0), bar(95, 195, 300, 215, order=1, colour=WHITE))
    )
    assert "█" not in found.human_sees
    assert "white" in found.summary


def test_the_summary_carries_the_coordinates_so_it_can_be_checked_by_hand():
    (found,) = covered_text(page(run("SECRET", order=0), bar(95, 195, 300, 215, order=1)))
    assert "95" in found.summary and "195" in found.summary


# --------------------------------------------------------------------------
# the things that must NOT be reported
# --------------------------------------------------------------------------


def test_a_shape_drawn_before_the_text_does_not_cover_it():
    """Z-order decides. A rectangle painted first is a background, and the text
    on top of it is perfectly legible."""
    assert covered_text(page(bar(95, 195, 300, 215, order=0), run("VISIBLE", order=1))) == []


def test_a_fully_transparent_shape_covers_nothing():
    assert (
        covered_text(page(run("SECRET", order=0), bar(95, 195, 300, 215, order=1, alpha=0.0))) == []
    )


def test_a_page_sized_fill_is_a_background_not_a_bar():
    assert covered_text(page(run("SECRET", order=0), bar(0, 0, 595, 842, order=1))) == []


def test_a_shape_that_misses_the_text_covers_nothing():
    assert covered_text(page(run("SECRET", order=0), bar(400, 500, 500, 520, order=1))) == []


def test_a_clip_narrows_what_a_bar_can_cover():
    """A shape's own box overstates it whenever a clipping path is in force.
    Sizing a bar by `bbox` rather than `visible_bbox` would report text that a
    reader looking at the page can see perfectly well."""
    (found,) = covered_text(
        page(
            run("SECRETS", order=0),
            bar(95, 195, 300, 215, order=1, clip=Rect(0, 0, 141, 842)),
        )
    )
    assert found.machine_reads == "SECR"


def test_a_shape_that_grazes_a_glyph_does_not_count_as_covering_it():
    """Two points of overlap on one letter is a rule drawn near a line, not a
    redaction, and reporting it would bury the real findings in noise."""
    assert covered_text(page(run("SECRET", order=0), bar(95, 195, 102, 215, order=1))) == []


def test_text_that_is_never_painted_is_not_reported_as_covered():
    """Render mode 3 text is invisible on its own account. It is a finding, but
    a different one, and counting it twice would be two names for one fact."""
    assert covered_text(page(run("SECRET", order=0, mode=3), bar(95, 195, 300, 215, order=1))) == []


# --------------------------------------------------------------------------
# partial coverage - the point of doing this with real widths
# --------------------------------------------------------------------------


def test_only_the_covered_characters_are_reported():
    """A bar over the first four letters is a finding about four letters."""
    (found,) = covered_text(page(run("SECRETS", order=0), bar(95, 195, 141, 215, order=1)))
    assert found.machine_reads == "SECR"


def test_the_uncovered_tail_is_named_so_the_reader_can_find_the_line():
    (found,) = covered_text(page(run("SECRETS", order=0), bar(95, 195, 141, 215, order=1)))
    assert "ETS" in found.summary


def test_two_bars_on_one_line_are_two_findings():
    found = covered_text(
        page(
            run("ONE TWO THREE", order=0),
            bar(95, 195, 135, 215, order=1),
            bar(175, 195, 215, 215, order=2),
        )
    )
    assert len(found) == 2
    # The second bar runs 175-215. The space at 170-180 and the final E at
    # 210-220 are each half covered, which is under the threshold, so the
    # finding is the three whole letters between them.
    assert [f.machine_reads for f in found] == ["ONE", "THR"]


def test_a_run_split_by_a_bar_reports_the_pieces_separately():
    """One bar, one gap, one bar again: three characters covered at each end
    and the middle legible. Reporting that as one span would be a lie about
    what the page shows."""
    found = covered_text(
        page(
            run("ABCDEFGHIJ", order=0),
            bar(95, 195, 131, 215, order=1),
            bar(165, 195, 205, 215, order=2),
        )
    )
    assert [f.machine_reads for f in found] == ["ABC", "HIJ"]


# --------------------------------------------------------------------------
# invisible render mode
# --------------------------------------------------------------------------


def test_render_mode_three_is_its_own_finding():
    (found,) = invisible_text(page(run("HIDDEN", order=0, mode=3)))
    assert found.detector == "invisible-text"
    assert found.basis is Basis.DIRECT
    assert found.machine_reads == "HIDDEN"
    assert found.human_sees == ""


def test_ordinary_text_is_not_reported_as_invisible():
    assert invisible_text(page(run("VISIBLE", order=0))) == []


def test_whitespace_only_invisible_text_is_not_worth_a_finding():
    assert invisible_text(page(run("   ", order=0, mode=3))) == []


# --------------------------------------------------------------------------
# the specimens
# --------------------------------------------------------------------------

COVERED = [
    "Wanda Testowa-Przyklad",
    "w.testowa@example.org",
    "+48 601 000 000",
    "ul. Przykladowa 12/3, 00-001 Warszawa",
]


@pytest.mark.parametrize(
    "specimen",
    ["libreoffice-writer-black-bars.pdf", "chrome-print-css-overlay.pdf"],
)
def test_a_failed_redaction_gives_one_finding_per_bar(specimen):
    found = covered_text(interpret_page(page_of(specimen)))
    assert len(found) == 4
    assert sorted(f.machine_reads.strip() for f in found) == sorted(COVERED)


@pytest.mark.parametrize(
    "specimen",
    ["libreoffice-writer-black-bars.pdf", "chrome-print-css-overlay.pdf"],
)
def test_the_labels_beside_the_bars_are_not_reported(specimen):
    found = covered_text(interpret_page(page_of(specimen)))
    everything = " ".join(f.machine_reads for f in found)
    for label in ("Name:", "Email:", "Telephone:", "Address:", "Filed", "Registry"):
        assert label not in everything


def test_the_properly_redacted_control_gives_nothing():
    """Same bars, same coordinates, text removed. This is the false positive
    that would cost the tool its credibility fastest."""
    assert covered_text(interpret_page(page_of("libreoffice-writer-properly-redacted.pdf"))) == []


def test_the_flattened_specimen_gives_nothing():
    assert covered_text(interpret_page(page_of("flattened-to-image.pdf"))) == []


def test_the_partial_specimen_reports_only_what_the_short_bars_cover():
    """The bars stop in the gap before each value's last word. Which words are
    covered was settled by poppler when the specimen was built, so this asserts
    the detector against a measurement this project did not make."""
    found = covered_text(interpret_page(page_of("libreoffice-writer-partial-bars.pdf")))
    reported = sorted(f.machine_reads.strip() for f in found)
    assert reported == sorted(
        [
            "Wanda",
            "w.testowa@example.org",
            "+48 601 000",
            "ul. Przykladowa 12/3, 00-001",
        ]
    )


def test_the_partial_specimen_leaves_the_last_word_of_each_value_legible():
    found = covered_text(interpret_page(page_of("libreoffice-writer-partial-bars.pdf")))
    everything = " ".join(f.machine_reads for f in found)
    for legible in ("Testowa-Przyklad", "Warszawa"):
        assert legible not in everything


# --------------------------------------------------------------------------
# text painted at no opacity
# --------------------------------------------------------------------------


def transparent(text: str, alpha: float, **kw) -> TextRun:
    gs = glyphs(text, **kw)
    return TextRun(
        text=text,
        glyphs=gs,
        bbox=Rect(gs[0].bbox.x0, gs[0].bbox.y0, gs[-1].bbox.x1, gs[-1].bbox.y1),
        font="F1",
        size=10,
        fill=BLACK,
        alpha=alpha,
        order=0,
    )


def test_text_painted_at_zero_alpha_is_invisible():
    """`color: transparent` is one CSS declaration. Chrome does not change the
    render mode for it - it sets `/ca 0` and paints normally - so a detector
    that looked only at `Tr` finds nothing, and one that looked only at colour
    finds black on white and calls it legible."""
    (found,) = invisible_text(page(transparent("RESERVE PRICE", 0.0)))
    assert found.detector == "invisible-text"
    assert found.basis is Basis.DIRECT
    assert found.machine_reads == "RESERVE PRICE"
    assert "opacity" in found.summary or "opaque" in found.summary


def test_barely_visible_text_is_reported_but_only_as_circumstantial():
    """A tenth of an opacity may still be readable on a good screen, and it is
    also how a watermark is set. The observation is certain; whether the gap
    exists is not."""
    (found,) = invisible_text(page(transparent("FAINT", 0.1)))
    assert found.basis is Basis.CIRCUMSTANTIAL
    assert "0.1" in found.summary


def test_ordinary_opaque_text_is_not_reported():
    assert invisible_text(page(transparent("VISIBLE", 1.0))) == []


def test_text_at_zero_alpha_is_not_also_reported_as_covered():
    """It is not under anything. It was never painted."""
    assert covered_text(page(transparent("HIDDEN", 0.0), bar(95, 195, 300, 215, order=1))) == []


def test_text_at_zero_alpha_is_not_also_a_colour_finding():
    assert low_contrast_text(page(transparent("HIDDEN", 0.0))) == []


# --------------------------------------------------------------------------
# text in the colour of what is behind it
# --------------------------------------------------------------------------

NAVY = Colour((0.10, 0.23, 0.37), "rgb")


def test_white_text_on_the_bare_page_is_reported():
    """A PDF has no page colour; the background is the paper, and the paper is
    white. White text on nothing is invisible and needs no shape to hide it."""
    (found,) = low_contrast_text(page(run("INVISIBLE", fill=WHITE)))
    assert found.detector == "low-contrast-text"
    assert found.machine_reads == "INVISIBLE"
    assert found.human_sees == ""


def test_black_text_on_the_bare_page_is_not_reported():
    assert low_contrast_text(page(run("VISIBLE", fill=BLACK))) == []


def test_text_the_colour_of_a_box_drawn_behind_it_is_reported():
    (found,) = low_contrast_text(
        page(bar(90, 190, 320, 220, order=0, colour=NAVY), run("HIDDEN", order=1, fill=NAVY))
    )
    assert found.machine_reads == "HIDDEN"
    assert "0.10" in found.summary or "#1a3b5e" in found.summary.lower()


def test_the_same_text_on_a_box_of_another_colour_is_not_reported():
    assert (
        low_contrast_text(
            page(bar(90, 190, 320, 220, order=0, colour=WHITE), run("READABLE", order=1, fill=NAVY))
        )
        == []
    )


def test_a_box_drawn_after_the_text_is_not_its_background():
    """A shape painted later is on top. That is `covered_text`'s finding, and
    calling it a colour match as well would be two names for one fact."""
    assert (
        low_contrast_text(
            page(run("HIDDEN", order=0, fill=NAVY), bar(90, 190, 320, 220, order=1, colour=NAVY))
        )
        == []
    )


def test_the_topmost_background_wins():
    """Two boxes behind the text: the later one is what the eye sees."""
    assert (
        low_contrast_text(
            page(
                bar(90, 190, 320, 220, order=0, colour=NAVY),
                bar(90, 190, 320, 220, order=1, colour=WHITE),
                run("READABLE", order=2, fill=NAVY),
            )
        )
        == []
    )


def test_an_exact_colour_match_is_direct_and_a_near_one_is_circumstantial():
    """A near match may still be legible on a good screen, so whether the gap
    exists at all is a judgement. An exact match is not."""
    (exact,) = low_contrast_text(page(run("A", fill=WHITE)))
    (near,) = low_contrast_text(page(run("B", fill=Colour((0.97, 0.97, 0.97), "rgb"))))
    assert exact.basis is Basis.DIRECT
    assert near.basis is Basis.CIRCUMSTANTIAL


def test_a_background_whose_colour_is_unreadable_is_not_assumed_to_be_paper():
    """ "We cannot tell what is behind this" and "it is white" are different
    answers, and only one of them is true. A pattern fill gives the first."""
    assert (
        low_contrast_text(
            page(
                bar(90, 190, 320, 220, order=0, colour=None),
                run("MAYBE", order=1, fill=WHITE),
            )
        )
        == []
    )


def test_an_image_behind_the_text_is_a_background_this_tool_cannot_read():
    """A photograph, a letterhead, a watermark. The tool does not know what
    colour the picture is where the glyph sits, and saying "white, the same as
    the paper" would be inventing the evidence rather than reading it."""
    backdrop = image(90, 190, 320, 220, order=0)
    assert (
        low_contrast_text(
            InterpretedPage(
                number=1,
                box=PAGE,
                shapes=(backdrop,),
                texts=(run("WHITE", order=1, fill=WHITE),),
            )
        )
        == []
    )


def test_an_image_behind_the_text_does_not_hide_a_fill_that_is_over_it():
    """Order still decides. A box painted on top of the picture is what the eye
    sees, and its colour is readable."""
    backdrop = image(90, 190, 320, 220, order=0)
    box = bar(90, 190, 320, 220, order=1, colour=WHITE)
    (found,) = low_contrast_text(
        InterpretedPage(
            number=1,
            box=PAGE,
            shapes=(backdrop, box),
            texts=(run("WHITE", order=2, fill=WHITE),),
        )
    )
    assert found.machine_reads == "WHITE"


def test_stroke_only_text_is_judged_on_its_stroke_colour():
    """Render mode 1 draws outlines and never fills. Comparing its fill colour
    to the background would judge a colour that is never put on the page."""
    on_paper = page(run("OUTLINE", mode=1, fill=BLACK, stroke=WHITE))
    (found,) = low_contrast_text(on_paper)
    assert found.machine_reads == "OUTLINE"

    visible = page(run("OUTLINE", mode=1, fill=WHITE, stroke=BLACK))
    assert low_contrast_text(visible) == []


def test_text_with_no_stated_colour_is_not_guessed_at():
    assert low_contrast_text(page(run("UNKNOWN", fill=None))) == []


def test_invisible_render_mode_is_not_also_a_colour_finding():
    assert low_contrast_text(page(run("HIDDEN", mode=3, fill=WHITE))) == []


# --------------------------------------------------------------------------
# text outside the visible page
# --------------------------------------------------------------------------


def test_text_beyond_the_page_box_is_reported():
    (found,) = off_page_text(page(run("OFFSTAGE", x=700, y=200)))
    assert found.detector == "off-page-text"
    assert found.basis is Basis.DIRECT
    assert found.machine_reads == "OFFSTAGE"


def test_text_below_the_page_box_is_reported():
    (found,) = off_page_text(page(run("BELOW", x=100, y=-40)))
    assert found.machine_reads == "BELOW"


def test_text_on_the_page_is_not_reported():
    assert off_page_text(page(run("ON PAGE", x=100, y=200))) == []


def test_only_the_part_of_a_run_that_is_off_the_page_is_reported():
    """A word straddling the edge is reported for the characters that fall off
    it and no others - the same per-glyph rule the bar detectors use. The first
    E still touches the page at x=585-595, so it is not among them."""
    (found,) = off_page_text(page(run("EDGE", x=585, y=200)))
    assert found.machine_reads == "DGE"


def test_text_clipped_entirely_away_is_off_the_page_too():
    """A glyph inside the paper but outside the clip in force when it was drawn
    is exactly as invisible as one past the margin."""
    clipped = TextRun(
        text="CLIPPED",
        glyphs=glyphs("CLIPPED", x=100, y=200),
        bbox=Rect(100, 200, 170, 210),
        font="F1",
        size=10,
        fill=BLACK,
        clip=Rect(0, 400, 595, 842),
        order=0,
    )
    (found,) = off_page_text(InterpretedPage(number=1, box=PAGE, shapes=(), texts=(clipped,)))
    assert found.machine_reads == "CLIPPED"


def test_a_glyph_merely_touching_the_edge_is_not_off_the_page():
    """Only glyphs with no overlap at all count, which keeps this quiet on the
    ordinary documents the tool will mostly be pointed at."""
    assert off_page_text(page(run("AB", x=575, y=200))) == []


# --------------------------------------------------------------------------
# text under an image
# --------------------------------------------------------------------------


def test_text_under_an_image_is_its_own_finding():
    (found,) = text_under_image(page(run("BENEATH", order=0), image(95, 195, 300, 215)))
    assert found.detector == "text-under-image"
    assert found.machine_reads == "BENEATH"


def test_text_under_an_image_is_not_also_reported_as_under_a_shape():
    assert covered_text(page(run("BENEATH", order=0), image(95, 195, 300, 215))) == []


def test_the_scanned_page_explanation_is_named_rather_than_ruled_out():
    """A page image with a text layer beneath it is what a scanner produces,
    and the two usually agree. The tool says so instead of implying a motive."""
    (found,) = text_under_image(page(run("BENEATH", order=0), image(95, 195, 300, 215)))
    assert "scan" in found.summary.lower()


# --------------------------------------------------------------------------
# the hidden-in-plain-sight specimen
# --------------------------------------------------------------------------

PLAIN = "libreoffice-writer-hidden-in-plain-sight.pdf"


def test_the_white_line_and_the_line_on_its_box_are_both_reported():
    found = low_contrast_text(interpret_page(page_of(PLAIN)))
    reads = [f.machine_reads for f in found]
    assert any("simply white" in r for r in reads)
    assert any("colour of the box" in r for r in reads)


def test_the_ordinary_black_line_of_that_specimen_is_not_reported():
    found = low_contrast_text(interpret_page(page_of(PLAIN)))
    assert not any("must not be reported" in f.machine_reads for f in found)


def test_the_line_below_the_crop_box_is_reported():
    (found,) = off_page_text(interpret_page(page_of(PLAIN)))
    assert "below the crop box" in found.machine_reads


def test_that_specimen_has_nothing_covered_and_nothing_invisible():
    """It hides everything by colour and position. A detector that fires on it
    for the wrong reason has found the right file for the wrong cause."""
    interpreted = interpret_page(page_of(PLAIN))
    assert covered_text(interpreted) == []
    assert invisible_text(interpreted) == []


@pytest.mark.parametrize(
    "specimen",
    [
        "libreoffice-writer-black-bars.pdf",
        "chrome-print-css-overlay.pdf",
        "libreoffice-writer-properly-redacted.pdf",
        "libreoffice-writer-partial-bars.pdf",
    ],
)
def test_the_bar_specimens_have_no_colour_or_position_findings(specimen):
    """The new detectors must stay silent on the files the old ones handle."""
    interpreted = interpret_page(page_of(specimen))
    assert low_contrast_text(interpreted) == []
    assert off_page_text(interpreted) == []


# --------------------------------------------------------------------------
# the transparent-text specimen
# --------------------------------------------------------------------------

TRANSPARENT_SPECIMEN = "chrome-transparent-text.pdf"


def test_the_transparent_line_of_the_specimen_is_reported():
    found = invisible_text(interpret_page(page_of(TRANSPARENT_SPECIMEN)))
    reads = " ".join(f.machine_reads for f in found)
    assert "reserve price is 4.2 million" in reads


def test_the_faded_line_of_the_specimen_is_reported_as_circumstantial():
    found = invisible_text(interpret_page(page_of(TRANSPARENT_SPECIMEN)))
    faded = [f for f in found if "one tenth opacity" in f.machine_reads]
    assert faded and all(f.basis is Basis.CIRCUMSTANTIAL for f in faded)


def test_the_ordinary_lines_of_that_specimen_are_not_reported():
    found = invisible_text(interpret_page(page_of(TRANSPARENT_SPECIMEN)))
    reads = " ".join(f.machine_reads for f in found)
    assert "must not be reported" not in reads
    assert "Only two of them" not in reads


def test_nothing_is_covered_or_low_contrast_in_that_specimen():
    """It hides by opacity alone. Every other detector must stay silent."""
    interpreted = interpret_page(page_of(TRANSPARENT_SPECIMEN))
    assert covered_text(interpreted) == []
    assert low_contrast_text(interpreted) == []
    assert off_page_text(interpreted) == []


# --------------------------------------------------------------------------
# the OCR-layer specimen
# --------------------------------------------------------------------------

SCAN = "redacted-scan-with-ocr.pdf"


def test_the_invisible_ocr_layer_is_reported_by_the_line_not_by_the_word():
    """tesseract writes one show-operation per word. Reporting per run turns
    one hidden line into eight findings - the same mistake `covered_text` made
    with Chrome, which writes one per glyph."""
    found = invisible_text(interpret_page(page_of(SCAN)))
    assert len(found) == 3, [f.machine_reads for f in found]


def test_the_redacted_figure_is_still_in_the_invisible_layer():
    """The box was painted on the picture after the OCR ran. The words are
    underneath it, complete, and nothing on the page says so."""
    found = invisible_text(interpret_page(page_of(SCAN)))
    reads = " ".join(f.machine_reads for f in found)
    assert "250,000 EUR" in reads


def test_the_words_of_a_line_keep_their_spacing_when_they_are_joined():
    found = invisible_text(interpret_page(page_of(SCAN)))
    assert any(f.machine_reads.startswith("Agreed figure:") for f in found)


def test_that_specimen_is_an_image_with_nothing_painted_over_visible_text():
    interpreted = interpret_page(page_of(SCAN))
    assert [s.kind for s in interpreted.shapes] == ["image", "image"]
    assert covered_text(interpreted) == []
    assert text_under_image(interpreted) == []


def test_a_gap_between_two_show_operations_becomes_a_space():
    """A producer that writes one operation per word emits no space between
    them - the gap is in the positioning. tesseract happens to write a trailing
    space in each, so the specimen never exercises this; Chrome does not, and
    neither do many others."""
    left = TextRun(
        text="Agreed",
        glyphs=glyphs("Agreed", x=100, y=200),
        bbox=Rect(100, 200, 160, 210),
        font="F1",
        size=10,
        render_mode=3,
        fill=BLACK,
        order=0,
    )
    right = TextRun(
        text="figure",
        glyphs=glyphs("figure", x=200, y=200),
        bbox=Rect(200, 200, 260, 210),
        font="F1",
        size=10,
        render_mode=3,
        fill=BLACK,
        order=1,
    )
    (found,) = invisible_text(InterpretedPage(number=1, box=PAGE, shapes=(), texts=(left, right)))
    assert found.machine_reads == "Agreed figure"


def test_glyphs_that_merely_touch_are_not_separated():
    """Chrome splits a word across operations with no gap at all. Putting a
    space in there would report a word that is not in the file."""
    left = TextRun(
        text="TRANSP",
        glyphs=glyphs("TRANSP", x=100, y=200),
        bbox=Rect(100, 200, 160, 210),
        font="F1",
        size=10,
        render_mode=3,
        fill=BLACK,
        order=0,
    )
    right = TextRun(
        text="ARENT",
        glyphs=glyphs("ARENT", x=160, y=200),
        bbox=Rect(160, 200, 210, 210),
        font="F1",
        size=10,
        render_mode=3,
        fill=BLACK,
        order=1,
    )
    (found,) = invisible_text(InterpretedPage(number=1, box=PAGE, shapes=(), texts=(left, right)))
    assert found.machine_reads == "TRANSPARENT"


def test_two_ways_of_being_invisible_on_one_line_are_two_findings():
    """A render mode that paints nothing and an opacity that paints nothing are
    different statements about the file. Merging them would give one finding
    that could only describe half of itself."""
    unpainted = TextRun(
        text="MODE",
        glyphs=glyphs("MODE", x=100, y=200),
        bbox=Rect(100, 200, 140, 210),
        font="F1",
        size=10,
        render_mode=3,
        fill=BLACK,
        order=0,
    )
    clear = TextRun(
        text="ALPHA",
        glyphs=glyphs("ALPHA", x=200, y=200),
        bbox=Rect(200, 200, 250, 210),
        font="F1",
        size=10,
        fill=BLACK,
        alpha=0.0,
        order=1,
    )
    found = invisible_text(InterpretedPage(number=1, box=PAGE, shapes=(), texts=(unpainted, clear)))
    assert sorted(f.machine_reads for f in found) == ["ALPHA", "MODE"]


# --------------------------------------------------------------------------
# the image-over-text specimen
# --------------------------------------------------------------------------

IMAGE_OVER = "libreoffice-writer-image-over-text.pdf"


def test_a_redaction_pasted_as_a_picture_is_found():
    """No path, no fill colour, no `re` and no `f*` - an image XObject placed
    by a matrix. Every shape-based detector here finds nothing on it."""
    (found,) = text_under_image(interpret_page(page_of(IMAGE_OVER)))
    assert found.machine_reads == "Ludmila Wieczorek-Test"


def test_no_shape_detector_sees_that_specimen():
    interpreted = interpret_page(page_of(IMAGE_OVER))
    assert covered_text(interpreted) == []
    assert [s.kind for s in interpreted.shapes] == ["image"]


def test_the_scan_explanation_is_still_named_on_a_real_file():
    (found,) = text_under_image(interpret_page(page_of(IMAGE_OVER)))
    assert "scan" in found.summary.lower()


def test_the_other_fields_of_that_specimen_are_not_reported():
    (found,) = text_under_image(interpret_page(page_of(IMAGE_OVER)))
    assert "SYN-2024-1102" not in found.machine_reads
    assert "no further action" not in found.machine_reads


def test_every_detector_now_has_a_specimen():
    """The gap that mattered most: two detectors were covered only by unit
    tests on hand-built pages, which is exactly the shape of the bug that
    started this project."""
    fired = set()
    for name in (
        "libreoffice-writer-black-bars.pdf",
        "chrome-print-css-overlay.pdf",
        "libreoffice-writer-partial-bars.pdf",
        "libreoffice-writer-hidden-in-plain-sight.pdf",
        "chrome-transparent-text.pdf",
        "redacted-scan-with-ocr.pdf",
        IMAGE_OVER,
    ):
        interpreted = interpret_page(page_of(name))
        for finding in (
            covered_text(interpreted)
            + text_under_image(interpreted)
            + invisible_text(interpreted)
            + low_contrast_text(interpreted)
            + off_page_text(interpreted)
        ):
            fired.add(finding.detector)
    assert fired == {
        "covered-text",
        "text-under-image",
        "invisible-text",
        "low-contrast-text",
        "off-page-text",
    }


# --------------------------------------------------------------------------
# the coverage edge
# --------------------------------------------------------------------------

EDGE = "coverage-edge.pdf"


def test_the_threshold_is_where_the_specimen_says_it_is():
    """Four single-character marks under bars covering 100%, 75%, 50% and 25%
    of them. A threshold has to be somewhere, and a file that records where
    makes moving it a decision rather than a drift."""
    found = covered_text(interpret_page(page_of(EDGE)))
    assert sorted(f.machine_reads for f in found) == ["A", "B"]


def test_a_mark_covered_by_a_quarter_is_not_reported():
    found = covered_text(interpret_page(page_of(EDGE)))
    assert "D" not in {f.machine_reads for f in found}


def test_the_uncovered_marks_are_named_in_the_line_context():
    found = covered_text(interpret_page(page_of(EDGE)))
    first = next(f for f in found if f.machine_reads == "A")
    assert "B C D" in first.summary


def test_one_character_is_reported_in_the_singular():
    """A report is read by a person."""
    found = covered_text(interpret_page(page_of(EDGE)))
    assert all(f.summary.startswith("1 character under") for f in found)


# --------------------------------------------------------------------------
# the text-on-a-picture specimen
# --------------------------------------------------------------------------

ON_IMAGE = "text-on-an-image.pdf"


def test_text_on_a_picture_is_not_reported_as_a_colour_finding():
    """Whether it is legible depends on what colour the picture is where the
    glyphs sit, and the content stream does not say."""
    assert low_contrast_text(interpret_page(page_of(ON_IMAGE))) == []


def test_but_the_tool_says_it_could_not_judge():
    """Silence and `nothing there` are different answers. This is the first
    one, said out loud."""
    note = " ".join(remarks(interpret_page(page_of(ON_IMAGE))))
    assert "not established" in note
    assert "picture" in note


def test_a_page_with_no_text_on_a_picture_gets_no_such_note():
    assert remarks(interpret_page(page_of("libreoffice-writer-black-bars.pdf"))) == []


def test_the_ordinary_lines_of_that_specimen_are_still_judged():
    """Only the glyphs on the picture are unjudgeable. The black text on paper
    beside them is compared as usual and comes back clean."""
    interpreted = interpret_page(page_of(ON_IMAGE))
    assert covered_text(interpreted) == []
    assert invisible_text(interpreted) == []
    note = " ".join(remarks(interpreted))
    assert "31 characters" in note, note


# --------------------------------------------------------------------------
# rotated text
#
# Every detector that reports a line groups the page's glyphs into lines
# first, and it used to do that by the bottom of the glyph box. That is exact
# for horizontal text and wrong for anything else: turn a line ninety degrees
# and every glyph has a different bottom edge and the same left edge, so one
# hidden line becomes one finding per letter. Measured on this specimen before
# the fix: 15 findings for one rotated line.
#
# The same failure Chrome's one-glyph-per-Tj produced on covered_text, from a
# completely different direction, and the grouping that fixed the first did
# not survive the second.
# --------------------------------------------------------------------------

ROTATED = "libreoffice-calc-rotated-headers.pdf"


def test_a_hidden_rotated_line_is_one_finding():
    found = low_contrast_text(interpret_page(page_of(ROTATED)))
    assert len(found) == 1


def test_the_rotated_line_is_read_in_order():
    """Sorting a rotated line by x puts every glyph in one place and the order
    is whatever the file happened to emit. It has to be sorted along the
    direction the text advances, which here is up the page."""
    (found,) = low_contrast_text(interpret_page(page_of(ROTATED)))
    assert found.machine_reads == "WITHDRAWN 196000"


def test_the_rotated_headers_that_are_visible_are_not_reported():
    """Rotated column headers are ordinary spreadsheet practice. Reporting the
    two black ones would make the detector useless on any wide table."""
    (found,) = low_contrast_text(interpret_page(page_of(ROTATED)))
    assert "Technical" not in found.machine_reads
    assert "Price" not in found.machine_reads


def test_the_horizontal_body_text_is_not_reported():
    found = low_contrast_text(interpret_page(page_of(ROTATED)))
    assert not any("Kowalski" in f.machine_reads for f in found)


def test_rotated_and_horizontal_text_never_share_a_line():
    """Two glyphs can sit at the same height and belong to lines running at
    right angles to each other. Bucketing on position alone merges them, and
    the report then quotes a line that does not exist anywhere on the page."""
    page = interpret_page(page_of(ROTATED))
    for line in _lines(page):
        texts = {round(_angle_of(run), 1) for _, run in line}
        assert len(texts) == 1, "one line held glyphs running at two angles"


def test_the_rotated_specimen_reports_nothing_else():
    """One file, one thing to prove. At the default column width the bidder
    names overflow and LibreOffice clips them, which `off-page-text` correctly
    reports - a true finding about a clipped letter of ordinary visible text,
    and nothing to do with rotation. The specimen was widened rather than the
    detector tuned, and no rule here separates a cell boundary
    from concealment."""
    page = interpret_page(page_of(ROTATED))
    assert covered_text(page) == []
    assert text_under_image(page) == []
    assert invisible_text(page) == []
    assert off_page_text(page) == []


def upright(text: str, *, x: float = 300, y: float = 400, height: float = 10) -> TextRun:
    """A run reading *down* the page, emitted in reverse order.

    Both halves matter. The direction makes the line vertical; the reversed
    emission makes the ordering testable, because a sort that keys on
    something constant along the line is stable and would quietly hand back
    whatever order the file happened to use.
    """
    gs = tuple(
        Glyph(
            char=ch,
            code=ord(ch),
            bbox=Rect(x, y - (i + 1) * height, x + 10, y - i * height),
            origin=(x, y - i * height),
        )
        for i, ch in enumerate(text)
    )
    return TextRun(
        text=text,
        glyphs=tuple(reversed(gs)),
        bbox=Rect(x, y - len(text) * height, x + 10, y),
        font="F1",
        size=10,
        render_mode=0,
        fill=WHITE,
        direction=(0.0, -1.0),
        order=0,
    )


def test_a_rotated_line_is_read_along_its_own_direction():
    """The specimen cannot catch this on its own: its glyphs happen to be
    emitted in reading order, so a sort keyed on anything constant along the
    line returns them unchanged. Reversing the emission is what makes the
    ordering rule testable."""
    page = InterpretedPage(number=1, box=PAGE, texts=(upright("HIDDEN"),), shapes=())
    (found,) = low_contrast_text(page)
    assert found.machine_reads == "HIDDEN"


def test_a_rotated_line_and_a_horizontal_one_never_merge():
    """Two glyphs can sit the same distance across lines running at right
    angles to each other. Without the angle in the key they share a bucket, and
    the report then quotes a line that exists nowhere on the page.

    Here both land at 200: the horizontal run by its height, the vertical one
    by its distance from the left edge.
    """
    page = InterpretedPage(
        number=1,
        box=PAGE,
        texts=(run("flat", y=200, fill=WHITE), upright("DOWN", x=200, y=500)),
        shapes=(),
    )
    reported = {f.machine_reads for f in low_contrast_text(page)}
    assert reported == {"flat", "DOWN"}


# --------------------------------------------------------------------------
# a cell boundary and a redaction by clipping
#
# The same mechanism, used for two purposes: text is drawn, a clipping path is
# in force, part of the text falls outside it. One is a column too narrow; the
# other is a hidden sentence, and the file says nothing about which.
#
# What can be said is what the rest of the line supports. A clipped tail beside
# visible text on the same line is what an overflow looks like; a line clipped
# away entirely is not. That is a weaker claim, so it is reported as
# circumstantial rather than suppressed - a redaction that clips only the
# second half of a line looks exactly like an overflow too, and deleting the
# finding would be deciding for the reader.
# --------------------------------------------------------------------------

OVERFLOW = "libreoffice-calc-clipped-overflow.pdf"
CROPPED = "libreoffice-writer-hidden-in-plain-sight.pdf"


def test_a_clipped_tail_beside_visible_text_is_circumstantial():
    found = off_page_text(interpret_page(page_of(OVERFLOW)))
    assert found, "the specimen no longer clips anything"
    assert all(f.basis is Basis.CIRCUMSTANTIAL for f in found)


def test_the_clipped_tail_says_the_rest_of_the_line_is_on_the_page():
    """A reader has to be able to tell this apart from the other kind without
    opening the file, so the summary says which of the two the evidence
    supports rather than leaving both findings identically worded."""
    found = off_page_text(interpret_page(page_of(OVERFLOW)))
    assert all("rest of the line" in f.summary for f in found)


def test_a_line_clipped_away_entirely_stays_direct():
    """The control. Nothing of this line is on the page, so there is no
    overflow reading available and the finding keeps its strength."""
    (found,) = off_page_text(interpret_page(page_of(CROPPED)))
    assert found.basis is Basis.DIRECT
    assert "rest of the line" not in found.summary


def test_the_overflowing_line_is_still_reported_at_all():
    """Not suppressed. A redaction that clips the second half of a line looks
    exactly like this, and a tool that deleted the finding would have decided
    for its reader."""
    found = off_page_text(interpret_page(page_of(OVERFLOW)))
    assert "".join(sorted(f.machine_reads for f in found))


# --------------------------------------------------------------------------
# the rule that has broken five times
#
# covered_text (Chrome, one glyph per Tj), invisible_text (tesseract, one
# operation per word), low_contrast_text and off_page_text (the rotated
# headers), _words_of (Chrome again, under a threshold measured in words).
#
# Every one was found by a producer doing something the previous fix had not
# anticipated, which means the sixth will be too. This asks the question
# directly instead of waiting for the producer: one line, every glyph its own
# show-operation, and every detector must report the line rather than the
# glyphs.
# --------------------------------------------------------------------------


def one_glyph_per_run(text: str, *, y: float = 200, **kw) -> tuple[TextRun, ...]:
    """The same line, written the way Chrome writes it."""
    return tuple(
        run(ch, x=100 + i * 10, y=y, **kw) for i, ch in enumerate(text)
    )


def test_no_detector_reports_per_show_operation():
    hidden = "HIDDEN"
    cases = {
        "covered-text": (
            InterpretedPage(
                number=1,
                box=PAGE,
                texts=one_glyph_per_run(hidden),
                shapes=(bar(95, 195, 200, 215, order=99),),
            ),
            covered_text,
        ),
        "invisible-text": (
            InterpretedPage(
                number=1, box=PAGE, texts=one_glyph_per_run(hidden, mode=3), shapes=()
            ),
            invisible_text,
        ),
        "low-contrast-text": (
            InterpretedPage(
                number=1, box=PAGE, texts=one_glyph_per_run(hidden, fill=WHITE), shapes=()
            ),
            low_contrast_text,
        ),
        "off-page-text": (
            InterpretedPage(
                number=1,
                box=Rect(0, 0, 90, 842),
                texts=one_glyph_per_run(hidden),
                shapes=(),
            ),
            off_page_text,
        ),
    }
    for name, (page, detector) in cases.items():
        found = detector(page)
        assert len(found) == 1, f"{name} reported {len(found)} findings for one line"
        assert found[0].machine_reads == hidden, f"{name} did not read the whole line"


def test_words_are_not_counted_per_show_operation():
    from unmasker.pdf.detectors import _words_of

    page = InterpretedPage(
        number=1, box=PAGE, texts=one_glyph_per_run("HIDDEN"), shapes=()
    )
    assert ["".join(g.char for g in w) for w in _words_of(page)] == ["HIDDEN"]
