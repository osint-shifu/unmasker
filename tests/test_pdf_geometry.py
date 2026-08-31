"""Matrices, rectangles and colour.

The matrix tests are not arithmetic exercises. Their numbers come out of
`tests/specimens/pdf/chrome-print-css-overlay.pdf`, measured in task 1: Chrome
writes `112 135 199 18 re` inside two nested transforms whose outer one flips
the Y axis, and the bar really is at x 154.5-303.75, y 656.67-670.17 on the
page. A matrix implementation that agrees with itself but not with that file is
the failure this file exists to prevent.
"""

import pytest

from unmasker.pdf.geometry import Colour, Matrix, Rect

# The two transforms Chrome emits, outermost first.
CHROME_OUTER = Matrix(0.23999999, 0, 0, -0.23999999, 0, 841.91998)
CHROME_INNER = Matrix(3.125, 0, 0, 3.125, 293.75, 293.75)


# --------------------------------------------------------------------------
# Matrix
# --------------------------------------------------------------------------


def test_identity_leaves_a_point_alone():
    assert Matrix.IDENTITY.apply(12.5, -3.0) == (12.5, -3.0)


def test_translation():
    assert Matrix(1, 0, 0, 1, 10, 20).apply(1, 2) == (11, 22)


def test_scale():
    assert Matrix(2, 0, 0, 3, 0, 0).apply(4, 5) == (8, 15)


def test_the_order_of_concatenation_is_the_one_cm_uses():
    """`cm` premultiplies: the new matrix applies before the existing CTM."""
    scale = Matrix(2, 0, 0, 2, 0, 0)
    move = Matrix(1, 0, 0, 1, 100, 0)
    # Scale first, then move: (3,0) -> (6,0) -> (106,0)
    assert scale.then(move).apply(3, 0) == (106, 0)
    # Move first, then scale: (3,0) -> (103,0) -> (206,0)
    assert move.then(scale).apply(3, 0) == (206, 0)


def test_the_chrome_transform_lands_where_the_specimen_says_it_does():
    ctm = CHROME_INNER.then(CHROME_OUTER)
    x0, y0 = ctm.apply(112, 135)
    x1, y1 = ctm.apply(112 + 199, 135 + 18)
    assert x0 == pytest.approx(154.5, abs=0.05)
    assert y0 == pytest.approx(670.17, abs=0.05)
    assert x1 == pytest.approx(303.75, abs=0.05)
    assert y1 == pytest.approx(656.67, abs=0.05)


def test_the_chrome_transform_flips_the_y_axis():
    """A negative determinant is why the glyphs carry `1 0 0 -1 .. Tm`."""
    assert CHROME_INNER.then(CHROME_OUTER).determinant < 0


def test_a_degenerate_matrix_is_reported_rather_than_dividing_by_zero():
    assert Matrix(0, 0, 0, 0, 0, 0).determinant == 0


# --------------------------------------------------------------------------
# Rect
# --------------------------------------------------------------------------


def test_a_rect_normalises_its_corners():
    """`re` may be given a negative width or height, and often is."""
    r = Rect.from_points([(10, 20), (0, 5)])
    assert (r.x0, r.y0, r.x1, r.y1) == (0, 5, 10, 20)


def test_area_and_emptiness():
    assert Rect(0, 0, 10, 4).area == 40
    assert Rect(3, 3, 3, 9).is_empty
    assert not Rect(0, 0, 1, 1).is_empty


def test_intersection():
    a = Rect(0, 0, 10, 10)
    b = Rect(5, 5, 20, 20)
    assert a.intersect(b) == Rect(5, 5, 10, 10)


def test_disjoint_rectangles_intersect_to_nothing():
    assert Rect(0, 0, 1, 1).intersect(Rect(5, 5, 6, 6)).is_empty


def test_contains_point():
    r = Rect(0, 0, 10, 10)
    assert r.contains(5, 5)
    assert r.contains(0, 0)
    assert not r.contains(11, 5)


def test_a_rect_the_size_of_the_page_can_be_recognised_as_such():
    page = Rect(0, 0, 595, 842)
    assert Rect(0, 0, 595, 842).covers_most_of(page)
    assert Rect(0, 0.028, 595.275, 841.861).covers_most_of(page)
    assert not Rect(117, 684, 268, 698).covers_most_of(page)


# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------


def test_gray_rgb_and_cmyk_all_arrive_as_rgb():
    assert Colour.from_operands([0.0]).rgb == (0.0, 0.0, 0.0)
    assert Colour.from_operands([1.0]).rgb == (1.0, 1.0, 1.0)
    assert Colour.from_operands([1.0, 0.0, 0.0]).rgb == (1.0, 0.0, 0.0)
    assert Colour.from_operands([0, 0, 0, 1]).rgb == (0.0, 0.0, 0.0)
    assert Colour.from_operands([0, 0, 0, 0]).rgb == (1.0, 1.0, 1.0)


def test_an_operand_count_we_do_not_understand_gives_an_unknown_colour():
    """A pattern or a Separation space is not something to guess at."""
    assert Colour.from_operands([]) is None
    assert Colour.from_operands([1, 2, 3, 4, 5]) is None


def test_luminance_orders_black_below_white():
    black = Colour.from_operands([0.0])
    white = Colour.from_operands([1.0])
    assert black.luminance < white.luminance
    assert black.luminance == pytest.approx(0.0)
    assert white.luminance == pytest.approx(1.0)


def test_two_colours_can_be_compared_for_closeness():
    """Task 4 needs 'is this text the colour of what is behind it', and that is
    a distance, not an equality: producers round differently."""
    a = Colour.from_operands([0.0, 0.0, 0.0])
    b = Colour.from_operands([0.004, 0.0, 0.004])
    assert a.close_to(b, tolerance=0.02)
    assert not a.close_to(Colour.from_operands([1.0, 1.0, 1.0]), tolerance=0.02)
