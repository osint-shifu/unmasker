"""The content-stream interpreter: what is painted on the page, and where.

Half of these are unit tests on streams written here; the other half run
against the committed specimens, whose coordinates were measured off the real
files in task 1. Both halves are needed, and the second is the one that counts:
task 1 exists because a fixture written from the PDF specification agrees with
the specification and not with any producer.

What task 1 established, and what these tests hold the interpreter to:

- LibreOffice draws a bar as `m`/`l`/`h` then `f*`, and emits no `re` for it.
- Chrome draws one as `re` then `f`, behind two nested transforms, the outer
  one flipping Y, with the fill colour set once for the whole page.
- The one `re` on a LibreOffice page is the clip, `re W* n`, and is not a bar.
"""

import pytest
from conftest import SPECIMEN_PDF, Stub, StubStream, page_of

from unmasker.pdf.geometry import Rect
from unmasker.pdf.interpreter import interpret_page, interpret_stream, page_box, page_content

A4 = Rect(0, 0, 595.276, 841.89)


def shapes_of(stream: str, **kw):
    return interpret_stream(stream.encode("latin-1"), box=A4, **kw).shapes


def fills(result):
    return [s for s in result if s.kind == "fill"]


# --------------------------------------------------------------------------
# paths and painting
# --------------------------------------------------------------------------


def test_a_rectangle_filled_with_f():
    (shape,) = shapes_of("0 0 0 rg 10 20 30 40 re f")
    assert shape.kind == "fill"
    assert shape.bbox == Rect(10, 20, 40, 60)
    assert shape.colour.rgb == (0, 0, 0)
    assert shape.operator == "f"


def test_a_polygon_filled_with_f_star_which_is_what_libreoffice_emits():
    (shape,) = shapes_of(
        "0 0 0 rg 193.1 684.239 m 117.5 684.239 l 117.5 698.489 l "
        "268.7 698.489 l 268.7 684.239 l 193.1 684.239 l h f*"
    )
    assert shape.bbox == Rect(117.5, 684.239, 268.7, 698.489)
    assert shape.even_odd is True


def test_a_path_ended_with_n_is_not_painted():
    assert list(shapes_of("0 0 0 rg 10 20 30 40 re n")) == []


def test_a_clipping_path_is_not_a_shape():
    """`re W* n` is the page clip in every LibreOffice file, and it is not a
    bar. Task 1 found this counted as the page's only `re`."""
    result = shapes_of("q 0 0.028 595.275 841.861 re W* n Q")
    assert fills(result) == []


def test_a_clip_narrows_what_a_later_fill_can_cover():
    (shape,) = shapes_of("q 0 0 100 100 re W n 0 0 0 rg 50 50 200 200 re f Q")
    assert shape.bbox == Rect(50, 50, 250, 250)
    assert shape.clip == Rect(0, 0, 100, 100)
    assert shape.visible_bbox == Rect(50, 50, 100, 100)


def test_the_painting_operators_that_fill():
    for op in ("f", "F", "f*", "B", "B*", "b", "b*"):
        got = fills(shapes_of(f"0 0 0 rg 1 1 10 10 re {op}"))
        assert len(got) == 1, op


def test_stroke_only_operators_do_not_produce_a_fill():
    for op in ("S", "s"):
        assert fills(shapes_of(f"0 0 0 RG 1 1 10 10 re {op}")) == [], op


def test_curves_contribute_their_control_points_to_the_bounds():
    """A conservative bound. Overstating a curve's extent is safer than
    understating it, and the report says the bound is what it is."""
    (shape,) = shapes_of("0 0 0 rg 0 0 m 10 100 20 100 30 0 c h f")
    assert shape.bbox.x0 == 0 and shape.bbox.x1 == 30
    assert shape.bbox.y1 == 100


def test_a_subpath_without_an_explicit_close_is_still_filled():
    (shape,) = shapes_of("0 0 0 rg 0 0 m 10 0 l 10 10 l f")
    assert shape.bbox == Rect(0, 0, 10, 10)


# --------------------------------------------------------------------------
# graphics state
# --------------------------------------------------------------------------


def test_q_and_Q_restore_the_transform():
    result = shapes_of("q 2 0 0 2 100 100 cm 0 0 0 rg 0 0 10 10 re f Q 0 0 10 10 re f")
    assert result[0].bbox == Rect(100, 100, 120, 120)
    assert result[1].bbox == Rect(0, 0, 10, 10)


def test_q_and_Q_restore_the_colour():
    result = shapes_of("0 0 0 rg q 1 0 0 rg 0 0 1 1 re f Q 2 2 1 1 re f")
    assert result[0].colour.rgb == (1, 0, 0)
    assert result[1].colour.rgb == (0, 0, 0)


def test_an_unbalanced_Q_does_not_raise():
    assert len(shapes_of("Q Q Q 0 0 0 rg 0 0 1 1 re f")) == 1


def test_nested_transforms_compose_the_way_chrome_writes_them():
    """The exact numbers from chrome-print-css-overlay.pdf."""
    (shape,) = shapes_of(
        ".23999999 0 0 -.23999999 0 841.91998 cm q "
        "3.125 0 0 3.125 293.75 293.75 cm 0 0 0 rg 112 135 199 18 re f Q"
    )
    assert shape.bbox.x0 == pytest.approx(154.5, abs=0.05)
    assert shape.bbox.x1 == pytest.approx(303.75, abs=0.05)
    assert shape.bbox.y0 == pytest.approx(656.67, abs=0.05)
    assert shape.bbox.y1 == pytest.approx(670.17, abs=0.05)


def test_colour_survives_across_intervening_operators():
    """Chrome sets `rg` once for the whole page; the bars inherit it."""
    result = shapes_of("0 0 0 rg 1 1 2 2 re f 5 5 2 2 re f 9 9 2 2 re f")
    assert [s.colour.rgb for s in result] == [(0, 0, 0)] * 3


def test_gray_and_cmyk_fills():
    assert shapes_of("0 g 0 0 1 1 re f")[0].colour.rgb == (0, 0, 0)
    assert shapes_of("0 0 0 1 k 0 0 1 1 re f")[0].colour.rgb == (0, 0, 0)


def test_an_unreadable_colour_is_recorded_as_unknown_not_guessed_as_black():
    (shape,) = shapes_of("/Pattern cs /P0 scn 0 0 10 10 re f")
    assert shape.colour is None


def test_a_fully_transparent_fill_is_marked_as_such():
    """`/GS0 gs` with `/ca 0` paints nothing. A bar with zero alpha covers
    nothing, and calling it a redaction would be a finding that is not there."""
    ext = {"GS0": {"ca": 0.0}}
    (shape,) = shapes_of("/GS0 gs 0 0 0 rg 0 0 10 10 re f", resources={"ExtGState": ext})
    assert shape.alpha == 0.0
    assert not shape.is_opaque


# --------------------------------------------------------------------------
# XObjects and images
# --------------------------------------------------------------------------


def test_a_form_xobject_is_walked_and_its_matrix_applied(form_resources):
    result = shapes_of("q 1 0 0 1 50 50 cm /Fm0 Do Q", resources=form_resources)
    (shape,) = fills(result)
    # The form draws 0 0 10 10 re f under its own /Matrix of [2 0 0 2 0 0].
    assert shape.bbox == Rect(50, 50, 70, 70)


def test_a_form_that_refers_to_itself_does_not_recurse_forever(cyclic_resources):
    result = interpret_stream(b"/Fm0 Do", box=A4, resources=cyclic_resources)
    assert any("recurs" in r for r in result.remarks)


def test_an_image_xobject_becomes_a_shape_covering_the_unit_square(image_resources):
    result = shapes_of("q 200 0 0 100 20 30 cm /Im0 Do Q", resources=image_resources)
    (shape,) = result
    assert shape.kind == "image"
    assert shape.bbox == Rect(20, 30, 220, 130)


def test_an_inline_image_becomes_a_shape():
    result = shapes_of("q 50 0 0 20 10 10 cm BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI Q")
    (shape,) = result
    assert shape.kind == "image"
    assert shape.bbox == Rect(10, 10, 60, 30)


# --------------------------------------------------------------------------
# honesty about coverage
# --------------------------------------------------------------------------


def test_an_operator_the_interpreter_does_not_know_is_remarked_not_ignored():
    """`CLAUDE.md`: 'nothing found' must not mean 'we stopped looking'."""
    result = interpret_stream(b"0 0 0 rg 1 1 2 2 re f /Nonsense zzz", box=A4)
    assert len(result.shapes) == 1
    assert any("zzz" in r for r in result.remarks)


def test_a_truncated_stream_yields_what_it_can_and_says_so():
    result = interpret_stream(b"0 0 0 rg 10 20 30 40 re f 1 2 m 3 4 l", box=A4)
    assert len(result.shapes) == 1
    assert any("unpainted" in r for r in result.remarks)


def test_a_known_operator_given_the_wrong_operands_is_not_called_unknown():
    """`1 2 3 re` is damage in a known operator, not an operator nobody has
    heard of, and a reader sent looking for the wrong thing is worse served
    than one told nothing."""
    result = interpret_stream(b"1 2 3 re f", box=A4)
    assert any("'re' needs 4" in r for r in result.remarks)
    assert not any("not understood" in r for r in result.remarks)


# --------------------------------------------------------------------------
# the specimens
# --------------------------------------------------------------------------


def test_libreoffice_specimen_has_four_black_bars_and_no_page_clip():
    result = interpret_page(page_of("libreoffice-writer-black-bars.pdf"))
    bars = [s for s in fills(result.shapes) if not s.bbox.covers_most_of(result.box)]
    assert len(bars) == 4
    assert all(s.colour.rgb == (0, 0, 0) for s in bars)
    assert all(s.operator == "f*" for s in bars), "LibreOffice fills even-odd"

    got = sorted((round(s.bbox.x0, 1), round(s.bbox.y0, 1)) for s in bars)
    assert got == [(114.8, 664.5), (117.5, 684.2), (119.0, 624.9), (123.1, 644.7)]


def test_libreoffice_specimen_emits_no_re_for_its_bars():
    """The finding that broke the original design. Its only `re` is the clip."""
    raw = page_of("libreoffice-writer-black-bars.pdf")
    result = interpret_page(raw)
    assert all(s.operator != "re" for s in result.shapes)
    assert result.counts["re"] == 1
    assert result.counts["f*"] == 4


def test_chrome_specimen_has_four_black_bars_at_the_transformed_coordinates():
    result = interpret_page(page_of("chrome-print-css-overlay.pdf"))
    bars = [s for s in fills(result.shapes) if not s.bbox.covers_most_of(result.box)]
    assert len(bars) == 4
    assert all(s.colour.rgb == (0, 0, 0) for s in bars)

    first = min(bars, key=lambda s: -s.bbox.y0)
    assert first.bbox.x0 == pytest.approx(154.5, abs=0.1)
    assert first.bbox.x1 == pytest.approx(303.75, abs=0.1)
    assert first.bbox.y0 == pytest.approx(656.67, abs=0.1)
    assert first.bbox.y1 == pytest.approx(670.17, abs=0.1)


def test_chrome_specimen_uses_re_where_libreoffice_uses_a_polygon():
    result = interpret_page(page_of("chrome-print-css-overlay.pdf"))
    assert result.counts["re"] == 5  # four bars and the page clip
    assert result.counts["f"] == 4


def test_the_properly_redacted_control_has_the_same_bars():
    """Same geometry, same colours. The difference is the text, not the shapes,
    which is exactly why a shape-only detector cannot tell them apart."""
    failed = interpret_page(page_of("libreoffice-writer-black-bars.pdf"))
    proper = interpret_page(page_of("libreoffice-writer-properly-redacted.pdf"))

    def geometry(result):
        return sorted(
            (round(s.bbox.x0, 2), round(s.bbox.y0, 2), round(s.bbox.x1, 2), round(s.bbox.y1, 2))
            for s in fills(result.shapes)
            if not s.bbox.covers_most_of(result.box)
        )

    assert geometry(failed) == geometry(proper)


def test_the_flattened_specimen_is_one_image_and_no_fills():
    result = interpret_page(page_of("flattened-to-image.pdf"))
    assert [s.kind for s in result.shapes] == ["image"]
    assert result.shapes[0].bbox.covers_most_of(result.box)


def test_every_specimen_is_interpreted_without_remarks_about_damage():
    """A remark is not a failure, but an unexpected one means the interpreter
    met something it could not read, and the report would have to say so."""
    for name in SPECIMEN_PDF:
        result = interpret_page(page_of(name))
        unexpected = [r for r in result.remarks if "unpainted" not in r]
        assert unexpected == [], f"{name}: {unexpected}"


# --------------------------------------------------------------------------
# getting at the content stream
# --------------------------------------------------------------------------


def test_page_content_reads_a_single_stream():
    page = Stub(Contents=StubStream(b"1 2 3 re f"))
    assert page_content(page) == b"1 2 3 re f"


def test_page_content_joins_an_array_of_streams():
    """HANDOFF.md found both forms in the first PDF it looked at. No committed
    specimen uses the array form, so this is the only thing holding it."""
    page = Stub(Contents=[StubStream(b"0 0 0 rg"), StubStream(b"1 1 5 5 re f")])
    assert interpret_stream(page_content(page), box=A4).shapes[0].colour.rgb == (0, 0, 0)


def test_page_content_separates_the_streams_it_joins():
    """Without a separator the last token of one stream and the first of the
    next fuse into a third operator that is in neither."""
    page = Stub(Contents=[StubStream(b"0 0 0 rg 1 1 5 5 re"), StubStream(b"f")])
    joined = page_content(page)
    assert b"ref" not in joined
    assert len(interpret_stream(joined, box=A4).shapes) == 1


def test_page_content_of_a_page_with_no_contents_is_empty():
    assert page_content(Stub()) == b""


def test_page_box_prefers_the_crop_box():
    assert page_box(Stub(MediaBox=[0, 0, 600, 800], CropBox=[10, 10, 500, 700])) == Rect(
        10, 10, 500, 700
    )
    assert page_box(Stub(MediaBox=[0, 0, 600, 800])) == Rect(0, 0, 600, 800)
