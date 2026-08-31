"""Text runs: where each glyph sits on the page, and which character it is.

The interpreter already walks the stream for shapes. Walking it once more for
text would mean two traversals that have to be made to agree afterwards; doing
both in one pass means the bar and the text under it come from the same reading
of the same bytes, which is the only way the overlap can be stated as fact.

The measurement that matters is at the bottom: on both specimens, the glyphs
spelling the covered values must land inside the bars that were measured off
those same files in task 1. That is the assertion the whole project rests on,
and until this file existed nothing checked it end to end.
"""

import pytest
from conftest import Stub, page_of

from unmasker.pdf.geometry import Rect
from unmasker.pdf.interpreter import interpret_page, interpret_stream

A4 = Rect(0, 0, 595.276, 841.89)

# Half an em for every code, so the arithmetic in a test is checkable by hand.
HALF_EM = Stub(Font=Stub(F1=Stub(Subtype="/TrueType", FirstChar=0, Widths=[500] * 256)))


def runs_of(stream: str, resources=HALF_EM):
    return interpret_stream(stream.encode("latin-1"), box=A4, resources=resources).texts


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------


def test_a_shown_string_lands_where_Td_put_it():
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td (AB) Tj ET")
    assert run.bbox.x0 == pytest.approx(100)
    assert run.bbox.x1 == pytest.approx(110)  # two glyphs at half an em of 10pt


def test_each_glyph_gets_its_own_box():
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td (AB) Tj ET")
    assert len(run.glyphs) == 2
    assert run.glyphs[0].bbox.x0 == pytest.approx(100)
    assert run.glyphs[0].bbox.x1 == pytest.approx(105)
    assert run.glyphs[1].bbox.x0 == pytest.approx(105)
    assert run.glyphs[1].bbox.x1 == pytest.approx(110)


def test_the_vertical_extent_comes_from_ascent_and_descent():
    """With no descriptor the stated defaults apply: 0.75 up, 0.25 down."""
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td (A) Tj ET")
    assert run.bbox.y0 == pytest.approx(197.5)
    assert run.bbox.y1 == pytest.approx(207.5)


def test_the_pen_advances_between_two_show_operations():
    a, b = runs_of("BT /F1 10 Tf 100 200 Td (AB) Tj (CD) Tj ET")
    assert a.bbox.x1 == pytest.approx(110)
    assert b.bbox.x0 == pytest.approx(110)


def test_TJ_adjustments_move_the_pen():
    """`tx = (w0 - Tj/1000) x Tfs`, so a *negative* number widens the gap. It
    reads backwards, and getting the sign wrong puts every kerned glyph on the
    wrong side of a bar."""
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td [(A) -1000 (B)] TJ ET")
    assert run.glyphs[0].bbox.x0 == pytest.approx(100)
    # 100 + 5 (the A) + 10 (one em of extra gap) = 115
    assert run.glyphs[1].bbox.x0 == pytest.approx(115)


def test_a_positive_TJ_adjustment_tightens():
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td [(A) 250 (B)] TJ ET")
    assert run.glyphs[1].bbox.x0 == pytest.approx(102.5)


def test_Tm_replaces_the_matrix_rather_than_adding_to_it():
    a, b = runs_of("BT /F1 10 Tf 100 200 Td (A) Tj 1 0 0 1 300 400 Tm (B) Tj ET")
    assert a.bbox.x0 == pytest.approx(100)
    assert b.bbox.x0 == pytest.approx(300)
    assert b.bbox.y0 == pytest.approx(397.5)


def test_T_star_moves_down_by_the_leading():
    a, b = runs_of("BT /F1 10 Tf 14 TL 100 200 Td (A) Tj T* (B) Tj ET")
    assert a.bbox.y0 == pytest.approx(197.5)
    assert b.bbox.y0 == pytest.approx(183.5)


def test_TD_sets_the_leading_as_well_as_moving():
    a, b = runs_of("BT /F1 10 Tf 100 200 Td (A) Tj 0 -12 TD (B) Tj T* (C) Tj ET")[:2]
    assert b.bbox.y0 == pytest.approx(185.5)


def test_character_and_word_spacing_widen_the_advance():
    (plain,) = runs_of("BT /F1 10 Tf 100 200 Td (AB) Tj ET")
    (spaced,) = runs_of("BT /F1 10 Tf 2 Tc 100 200 Td (AB) Tj ET")
    assert plain.bbox.x1 == pytest.approx(110)
    # A at 100-105, pen to 107, B at 107-112, pen to 114. The box is where the
    # ink ends, not where the pen did: the spacing after the last glyph is not
    # part of what the glyph covers, and counting it would make every run read
    # as slightly wider than it is.
    assert spaced.bbox.x1 == pytest.approx(112)


def test_word_spacing_applies_only_to_the_space_byte():
    (run,) = runs_of("BT /F1 10 Tf 5 Tw 100 200 Td (A B) Tj ET")
    # three glyphs at 5pt, plus 5pt of word spacing on the single space
    assert run.bbox.x1 == pytest.approx(120)


def test_horizontal_scaling_stretches_the_run():
    (run,) = runs_of("BT /F1 10 Tf 200 Tz 100 200 Td (AB) Tj ET")
    assert run.bbox.x1 == pytest.approx(120)


def test_the_ctm_is_applied_to_text_as_well_as_to_shapes():
    (run,) = runs_of("2 0 0 2 0 0 cm BT /F1 10 Tf 100 200 Td (AB) Tj ET")
    assert run.bbox.x0 == pytest.approx(200)
    assert run.bbox.x1 == pytest.approx(220)


# --------------------------------------------------------------------------
# render mode
# --------------------------------------------------------------------------


def test_the_render_mode_is_carried_on_the_run():
    (run,) = runs_of("BT /F1 10 Tf 3 Tr 100 200 Td (A) Tj ET")
    assert run.render_mode == 3
    assert run.is_invisible


def test_mode_zero_is_the_default_and_is_not_invisible():
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td (A) Tj ET")
    assert run.render_mode == 0
    assert not run.is_invisible


def test_mode_seven_is_clip_only_and_paints_nothing():
    (run,) = runs_of("BT /F1 10 Tf 7 Tr 100 200 Td (A) Tj ET")
    assert run.is_invisible


# --------------------------------------------------------------------------
# honesty
# --------------------------------------------------------------------------


def test_a_run_from_a_font_with_no_widths_admits_its_extent_is_estimated():
    resources = Stub(Font=Stub(F1=Stub(Subtype="/TrueType")))
    (run,) = runs_of("BT /F1 10 Tf 100 200 Td (AB) Tj ET", resources=resources)
    assert run.widths_estimated


def test_a_Tf_naming_a_font_that_is_not_there_still_produces_a_run():
    result = interpret_stream(b"BT /Missing 10 Tf 100 200 Td (AB) Tj ET", box=A4, resources=Stub())
    assert len(result.texts) == 1
    assert result.texts[0].widths_estimated
    assert any("Missing" in r for r in result.remarks)


# --------------------------------------------------------------------------
# the specimens: does the text land under the bars?
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
def test_the_text_of_a_specimen_is_reconstructed_from_its_own_codes(specimen):
    result = interpret_page(page_of(specimen))
    body = "".join(run.text for run in result.texts)
    for value in COVERED:
        assert value in body, value


@pytest.mark.parametrize(
    "specimen",
    ["libreoffice-writer-black-bars.pdf", "chrome-print-css-overlay.pdf"],
)
def test_every_covered_value_lies_inside_a_bar(specimen):
    """The assertion the project rests on, and the first time it is checked
    with real extents rather than with the start point of each run."""
    result = interpret_page(page_of(specimen))
    bars = [s for s in result.shapes if s.kind == "fill" and not s.bbox.covers_most_of(result.box)]
    assert len(bars) == 4

    for value in COVERED:
        glyphs = _glyphs_spelling(result.texts, value)
        assert glyphs, f"{value} not found among the glyphs"
        for glyph in glyphs:
            assert any(_inside(glyph.bbox, bar.bbox) for bar in bars), (
                f"{value!r}: glyph {glyph.char!r} at {glyph.bbox} is under no bar"
            )


@pytest.mark.parametrize(
    "specimen",
    ["libreoffice-writer-black-bars.pdf", "chrome-print-css-overlay.pdf"],
)
def test_the_text_that_was_not_redacted_lies_under_no_bar(specimen):
    """The other half. A detector that flags these has learned nothing."""
    result = interpret_page(page_of(specimen))
    bars = [s for s in result.shapes if s.kind == "fill" and not s.bbox.covers_most_of(result.box)]
    for value in ("17 April 2024", "SYN-2024-0417"):
        for glyph in _glyphs_spelling(result.texts, value):
            assert not any(_inside(glyph.bbox, bar.bbox) for bar in bars), (
                f"{value!r}: glyph {glyph.char!r} was reported as covered"
            )


def _glyphs_spelling(runs, value):
    """Every glyph of the first occurrence of `value`, across run boundaries."""
    glyphs = [g for run in runs for g in run.glyphs]
    text = "".join(g.char for g in glyphs)
    at = text.find(value)
    return glyphs[at : at + len(value)] if at >= 0 else []


def _inside(glyph: Rect, bar: Rect, share: float = 0.6) -> bool:
    overlap = glyph.intersect(bar)
    return not overlap.is_empty and overlap.area >= glyph.area * share
