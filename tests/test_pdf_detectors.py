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
    covered_text,
    invisible_text,
    low_contrast_text,
    off_page_text,
    text_under_image,
)
from unmasker.pdf.geometry import BLACK, WHITE, Colour, Rect
from unmasker.pdf.interpreter import Glyph, InterpretedPage, Shape, TextRun, interpret_page

PAGE = Rect(0, 0, 595, 842)


def glyphs(text: str, x: float = 100, y: float = 200, width: float = 10) -> tuple:
    return tuple(
        Glyph(char=ch, code=ord(ch), bbox=Rect(x + i * width, y, x + (i + 1) * width, y + 10))
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
    """"We cannot tell what is behind this" and "it is white" are different
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
    (found,) = off_page_text(
        InterpretedPage(number=1, box=PAGE, shapes=(), texts=(clipped,))
    )
    assert found.machine_reads == "CLIPPED"


def test_a_glyph_merely_touching_the_edge_is_not_off_the_page():
    """Only glyphs with no overlap at all count, which keeps this quiet on the
    ordinary documents the tool will mostly be pointed at."""
    assert off_page_text(page(run("AB", x=575, y=200))) == []


# --------------------------------------------------------------------------
# text under an image
# --------------------------------------------------------------------------


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
