"""Matrices, rectangles and colour, in page space.

Nothing here decides anything. A `Colour` knows its luminance and whether it is
close to another colour; it does not know whether it is "a redaction bar". That
judgement belongs to a detector, and keeping it out of the geometry is what lets
the report show a reader the numbers it used.

Page space is PDF user space: points, origin at the bottom-left of the page,
Y increasing upward. Every coordinate that leaves the interpreter is in it,
because the alternative - reporting the operand values a producer happened to
write - is wrong by a factor of 0.75 and a Y flip on any file Chrome made.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Matrix:
    """A PDF transformation matrix, `[a b c d e f]`.

        | a  b  0 |
        | c  d  0 |
        | e  f  1 |

    so a point maps to `(a·x + c·y + e, b·x + d·y + f)`.
    """

    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    #: Declared here and assigned below the class, because the value is a
    #: Matrix and cannot be built until the class exists.
    IDENTITY: ClassVar[Matrix]

    def then(self, outer: Matrix) -> Matrix:
        """This transform applied first, then `outer`.

        The order `cm` uses: the operand premultiplies the current CTM, so a
        `cm` inside a `q` block sits *inside* the transforms already in force.
        """
        return Matrix(
            self.a * outer.a + self.b * outer.c,
            self.a * outer.b + self.b * outer.d,
            self.c * outer.a + self.d * outer.c,
            self.c * outer.b + self.d * outer.d,
            self.e * outer.a + self.f * outer.c + outer.e,
            self.e * outer.b + self.f * outer.d + outer.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    @property
    def determinant(self) -> float:
        """Zero for a degenerate transform; negative when the axes are flipped."""
        return self.a * self.d - self.b * self.c

    @property
    def scale(self) -> float:
        """Roughly how many page points one unit becomes. Used for text extents."""
        return math.sqrt(abs(self.determinant)) or 0.0


Matrix.IDENTITY = Matrix(1, 0, 0, 1, 0, 0)


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @staticmethod
    def from_points(points) -> Rect:
        """The bounding box of any set of points, corners in any order.

        `re` is routinely given a negative width or height, and a path's points
        arrive in drawing order rather than sorted, so normalising here is not
        defensive programming - it is the common case.
        """
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def intersect(self, other: Rect) -> Rect:
        return Rect(
            max(self.x0, other.x0),
            max(self.y0, other.y0),
            min(self.x1, other.x1),
            min(self.y1, other.y1),
        )

    def overlaps(self, other: Rect) -> bool:
        return not self.intersect(other).is_empty

    def covers_most_of(self, page: Rect, fraction: float = 0.9) -> bool:
        """Whether this is page-sized.

        The page clip is a filled-looking rectangle in every file, and it is
        never a redaction bar. `filetrail`'s lesson about context applies: the
        shape alone cannot say, but its size against the page can.
        """
        return self.width >= page.width * fraction and self.height >= page.height * fraction


@dataclass(frozen=True)
class Colour:
    rgb: tuple[float, float, float]
    space: str
    """How it arrived: `gray`, `rgb`, `cmyk`. Kept because the report says how
    it knows, and 'the file said 0 g' is a different sentence from '0 0 0 rg'."""

    @staticmethod
    def from_operands(operands) -> Colour | None:
        """Read a colour from the operands of `g`, `rg`, `k`, `sc` or `scn`.

        Returns None when the operand count is not one this can read - a
        Pattern, a Separation, an N-channel space. That is deliberately not a
        guess: an unknown colour reported as black would let the tool claim a
        black bar it never saw.
        """
        try:
            values = [float(v) for v in operands]
        except (TypeError, ValueError):
            return None

        if len(values) == 1:
            g = _clamp(values[0])
            return Colour((g, g, g), "gray")
        if len(values) == 3:
            red, green, blue = (_clamp(v) for v in values)
            return Colour((red, green, blue), "rgb")
        if len(values) == 4:
            c, m, y, k = (_clamp(v) for v in values)
            return Colour(((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)), "cmyk")
        return None

    @property
    def luminance(self) -> float:
        """Rec. 709 relative luminance, on the same 0-1 scale as the channels."""
        r, g, b = self.rgb
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def close_to(self, other: Colour | None, tolerance: float = 0.02) -> bool:
        """Whether two colours would look the same.

        A distance rather than an equality, because producers round: text
        written as `0.003 0.003 0.003 rg` over a fill of `0 0 0 rg` is the same
        black to every eye that will ever look at it.
        """
        if other is None:
            return False
        return all(abs(x - y) <= tolerance for x, y in zip(self.rgb, other.rgb, strict=True))


def _clamp(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


BLACK = Colour((0.0, 0.0, 0.0), "gray")
WHITE = Colour((1.0, 1.0, 1.0), "gray")
