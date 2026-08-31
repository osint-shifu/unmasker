"""The content-stream interpreter: what is painted on a page, and where.

`pypdf` owns the object model, decompression, font decoding and text
extraction. This module owns the other half: replaying the drawing operators
with a graphics state, so that every painted region arrives in page
coordinates. `HANDOFF.md` argues that split; task 1 proved it is necessary.

## What task 1 forced

Three things, each of which would otherwise have produced a detector that
reports nothing on the archetypal case while its test suite stays green.

**A bar is not a rectangle operator.** LibreOffice draws every one of its bars
as `m`/`l`/`h` then `f*`, and emits no `re` for them at all - the single `re` on
its page is the clip. So this interpreter accumulates a *path* from `m`, `l`,
`c`, `v`, `y`, `h` and `re` alike, and a shape is any path that reaches a
painting operator. `n`, `W n` and `W* n` end a path without painting it, and
those are clips, not bars.

**The operands are not coordinates.** Chrome nests two transforms whose outer
one flips Y. Every point is put through the CTM as it is read, so nothing
downstream ever sees a producer's raw numbers.

**Colour is state, not an adjacent token.** Chrome sets `rg` once for the whole
page; text and bars share it and no `rg` precedes any fill. The state is
tracked through `q`/`Q`, never matched.

## Honesty about coverage

An operator this cannot read produces a remark, not silence. `CLAUDE.md`:
"nothing found" must never be allowed to mean "we stopped looking", and the
only layer that knows the interpreter gave up is the interpreter.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .geometry import BLACK, Colour, Matrix, Rect
from .tokens import InlineImage, Name, Operator, tokenize

# Operators that paint the current path, and how.
FILL_OPS = {"f": False, "F": False, "f*": True, "B": False, "B*": True, "b": False, "b*": True}
STROKE_OPS = {"S", "s", "B", "B*", "b", "b*"}
PAINT_OPS = set(FILL_OPS) | STROKE_OPS | {"n"}

# Known and deliberately not acted on. Listed so that a genuinely unknown
# operator can be told apart from one this does not need yet - the difference
# between "read and ignored" and "not understood" is the whole point of the
# remarks.
IGNORED = {
    # text: read by pypdf, and by the text-run pass that will join to it
    "BT",
    "ET",
    "Tc",
    "Tw",
    "Tz",
    "TL",
    "Ts",
    "Td",
    "TD",
    "Tm",
    "T*",
    "Tj",
    "TJ",
    "'",
    '"',
    "Tf",
    "Tr",
    # marked content and compatibility sections
    "BMC",
    "BDC",
    "EMC",
    "BX",
    "EX",
    "MP",
    "DP",
    # line and rendering parameters that do not move anything
    "w",
    "J",
    "j",
    "M",
    "d",
    "ri",
    "i",
    # type 3 glyph metrics
    "d0",
    "d1",
    # shading: painted, but its extent is the clip, which is already tracked
    "sh",
}

# How many operands each operator needs. A known operator that arrives short is
# damage, and saying "not understood" about it would point the reader at the
# wrong thing entirely.
ARITY = {"cm": 6, "m": 2, "l": 2, "c": 6, "v": 4, "y": 4, "re": 4, "rg": 3, "k": 4, "g": 1}

MAX_FORM_DEPTH = 12


@dataclass(frozen=True)
class Shape:
    """One painted region, in page coordinates."""

    kind: str
    """`fill`, `stroke` or `image`."""

    operator: str
    """The operator that painted it. Kept because it is evidence: `f*` says
    LibreOffice, `f` after a `re` says Chrome, and a report that names the
    operator can be checked against the file by hand."""

    points: tuple[tuple[float, float], ...]
    bbox: Rect
    colour: Colour | None
    clip: Rect | None
    alpha: float = 1.0
    even_odd: bool = False

    @property
    def visible_bbox(self) -> Rect:
        """What the shape can actually cover, once its clip is applied."""
        return self.bbox.intersect(self.clip) if self.clip else self.bbox

    @property
    def is_opaque(self) -> bool:
        """Whether it hides what is beneath it. A bar at zero alpha does not."""
        return self.alpha >= 0.999


@dataclass
class InterpretedPage:
    number: int
    box: Rect
    shapes: tuple[Shape, ...] = ()
    remarks: tuple[str, ...] = ()
    counts: Counter = field(default_factory=Counter)


@dataclass
class _State:
    ctm: Matrix
    clip: Rect
    fill: Colour | None = BLACK
    stroke: Colour | None = BLACK
    fill_alpha: float = 1.0
    stroke_alpha: float = 1.0
    fill_space: str | None = "DeviceGray"
    stroke_space: str | None = "DeviceGray"

    def copy(self) -> _State:
        return _State(**vars(self))


def _resolve(obj):
    """Follow a pypdf indirect reference, or pass a plain value through."""
    getter = getattr(obj, "get_object", None)
    return getter() if callable(getter) else obj


def _entry(mapping, key):
    """Look up `key` in a PDF dictionary, with or without its leading slash."""
    if mapping is None:
        return None
    mapping = _resolve(mapping)
    try:
        if key in mapping:
            return _resolve(mapping[key])
        slashed = "/" + key
        if slashed in mapping:
            return _resolve(mapping[slashed])
    except TypeError:
        return None
    return None


def _plain(value) -> str | None:
    """A `/Name` as plain text, whatever object model it arrived in."""
    if isinstance(value, Name):
        return value.value
    if isinstance(value, str):
        return value[1:] if value.startswith("/") else value
    return None


def _numbers(values) -> list[float] | None:
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return None
    return out


class _Interpreter:
    def __init__(self, box: Rect, remarks: list[str], counts: Counter) -> None:
        self.box = box
        self.shapes: list[Shape] = []
        self.remarks = remarks
        self.counts = counts
        self._unknown: set[str] = set()

    # -- remarks ---------------------------------------------------------

    def note(self, text: str) -> None:
        if text not in self.remarks:
            self.remarks.append(text)

    # -- the machine -----------------------------------------------------

    def run(self, data: bytes, state: _State, resources, chain: tuple) -> None:
        operands: list = []
        path: list[tuple[float, float]] = []
        subpath_start: tuple[float, float] | None = None
        stack: list[_State] = []
        pending_clip: bool | None = None

        def point(x: float, y: float) -> tuple[float, float]:
            return state.ctm.apply(x, y)

        for token in tokenize(data):
            if isinstance(token, InlineImage):
                self.counts["BI"] += 1
                self.shapes.append(self._unit_square(state, "BI"))
                operands = []
                continue

            if not isinstance(token, Operator):
                operands.append(token)
                continue

            op = token.value
            self.counts[op] += 1
            nums = _numbers(operands)

            need = ARITY.get(op)
            if need is not None and (nums is None or len(nums) < need):
                self.note(
                    f"operator {op!r} needs {need} numeric operands but was given "
                    f"{len(operands)}; it was skipped"
                )
                operands = []
                continue

            # -- graphics state ---------------------------------------
            if op == "q":
                stack.append(state.copy())
            elif op == "Q":
                if stack:
                    state = stack.pop()
                else:
                    self.note("a Q with no matching q; the state stack was already empty")
            elif op == "cm":
                state.ctm = Matrix(*nums[-6:]).then(state.ctm)
            elif op == "gs":
                self._apply_extgstate(state, operands, resources)

            # -- colour ------------------------------------------------
            elif op in ("g", "rg", "k"):
                state.fill = Colour.from_operands(nums or [])
                state.fill_space = {"g": "DeviceGray", "rg": "DeviceRGB", "k": "DeviceCMYK"}[op]
            elif op in ("G", "RG", "K"):
                state.stroke = Colour.from_operands(nums or [])
            elif op == "cs":
                state.fill_space = _plain(operands[-1]) if operands else None
                state.fill = self._initial_colour(state.fill_space)
            elif op == "CS":
                state.stroke_space = _plain(operands[-1]) if operands else None
                state.stroke = self._initial_colour(state.stroke_space)
            elif op in ("sc", "scn"):
                state.fill = Colour.from_operands(nums) if nums is not None else None
            elif op in ("SC", "SCN"):
                state.stroke = Colour.from_operands(nums) if nums is not None else None

            # -- path construction -------------------------------------
            elif op == "m":
                subpath_start = point(*nums[-2:])
                path.append(subpath_start)
            elif op == "l":
                path.append(point(*nums[-2:]))
            elif op == "c":
                # Control points are included, which overstates the curve's
                # extent. A bound that is too large is safe here: it can make
                # the tool say "this shape reaches the text", never the reverse.
                path += [
                    point(nums[-6], nums[-5]),
                    point(nums[-4], nums[-3]),
                    point(nums[-2], nums[-1]),
                ]
            elif op in ("v", "y"):
                path += [point(nums[-4], nums[-3]), point(nums[-2], nums[-1])]
            elif op == "h":
                if subpath_start is not None:
                    path.append(subpath_start)
            elif op == "re":
                x, y, w, h = nums[-4:]
                path += [point(x, y), point(x + w, y), point(x + w, y + h), point(x, y + h)]
                subpath_start = point(x, y)

            # -- clipping ----------------------------------------------
            elif op in ("W", "W*"):
                pending_clip = op == "W*"

            # -- painting ----------------------------------------------
            elif op in PAINT_OPS:
                self._paint(op, path, state)
                if pending_clip is not None and path:
                    state.clip = state.clip.intersect(Rect.from_points(path))
                pending_clip = None
                path, subpath_start = [], None

            # -- xobjects ----------------------------------------------
            elif op == "Do":
                self._do(operands, state, resources, chain)

            elif op in IGNORED:
                pass
            else:
                if op not in self._unknown:
                    self._unknown.add(op)
                    self.note(f"operator {op!r} was not understood and its effect is unknown")

            operands = []

        if path:
            self.note(
                f"the stream ended with {len(path)} unpainted path point(s); it may be truncated"
            )

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _initial_colour(space: str | None) -> Colour | None:
        """A `cs` resets the colour to its space's initial value.

        Device spaces start at black. A Pattern or a space this cannot read
        starts at a colour we do not know, and None says so rather than
        guessing black - which would let the tool claim a bar it never saw.
        """
        return (
            BLACK
            if space in ("DeviceGray", "DeviceRGB", "DeviceCMYK", "CalGray", "CalRGB")
            else None
        )

    def _paint(self, op: str, path: list, state: _State) -> None:
        if op == "n" or not path:
            return
        bbox = Rect.from_points(path)
        if op in FILL_OPS:
            self.shapes.append(
                Shape(
                    kind="fill",
                    operator=op,
                    points=tuple(path),
                    bbox=bbox,
                    colour=state.fill,
                    clip=state.clip,
                    alpha=state.fill_alpha,
                    even_odd=FILL_OPS[op],
                )
            )
        if op in STROKE_OPS:
            self.shapes.append(
                Shape(
                    kind="stroke",
                    operator=op,
                    points=tuple(path),
                    bbox=bbox,
                    colour=state.stroke,
                    clip=state.clip,
                    alpha=state.stroke_alpha,
                )
            )

    def _unit_square(self, state: _State, operator: str) -> Shape:
        """An image occupies the unit square, placed by the CTM."""
        corners = [state.ctm.apply(x, y) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
        return Shape(
            kind="image",
            operator=operator,
            points=tuple(corners),
            bbox=Rect.from_points(corners),
            colour=None,
            clip=state.clip,
            alpha=state.fill_alpha,
        )

    def _apply_extgstate(self, state: _State, operands, resources) -> None:
        name = _plain(operands[-1]) if operands else None
        entry = _entry(_entry(resources, "ExtGState"), name) if name else None
        if entry is None:
            if name:
                self.note(f"graphics state /{name} was named but could not be resolved")
            return
        for key, attr in (("ca", "fill_alpha"), ("CA", "stroke_alpha")):
            value = _entry(entry, key)
            if value is not None:
                try:
                    setattr(state, attr, float(value))
                except (TypeError, ValueError):
                    pass

    def _do(self, operands, state: _State, resources, chain: tuple) -> None:
        name = _plain(operands[-1]) if operands else None
        if not name:
            return
        xobject = _entry(_entry(resources, "XObject"), name)
        if xobject is None:
            self.note(f"XObject /{name} was drawn but could not be resolved")
            return

        subtype = _plain(_entry(xobject, "Subtype"))
        if subtype == "Image":
            self.shapes.append(self._unit_square(state, "Do"))
            return
        if subtype != "Form":
            self.note(f"XObject /{name} has subtype /{subtype}, which is not handled")
            return

        key = id(xobject)
        if key in chain:
            self.note(f"form /{name} recurses into itself; the cycle was not followed")
            return
        if len(chain) >= MAX_FORM_DEPTH:
            self.note(f"forms nest more than {MAX_FORM_DEPTH} deep; the rest was not followed")
            return

        try:
            data = xobject.get_data()
        except Exception as exc:
            self.note(f"form /{name} could not be decompressed: {exc}")
            return

        inner = state.copy()
        matrix = _numbers(_entry(xobject, "Matrix") or [])
        if matrix and len(matrix) >= 6:
            inner.ctm = Matrix(*matrix[:6]).then(inner.ctm)
        bbox = _numbers(_entry(xobject, "BBox") or [])
        if bbox and len(bbox) >= 4:
            corners = [
                inner.ctm.apply(x, y)
                for x, y in (
                    (bbox[0], bbox[1]),
                    (bbox[2], bbox[1]),
                    (bbox[2], bbox[3]),
                    (bbox[0], bbox[3]),
                )
            ]
            inner.clip = inner.clip.intersect(Rect.from_points(corners))

        self.run(data, inner, _entry(xobject, "Resources") or resources, chain + (key,))


def interpret_stream(
    data: bytes,
    *,
    box: Rect,
    resources=None,
    ctm: Matrix | None = None,
    number: int = 1,
) -> InterpretedPage:
    """Replay `data` and return everything it paints, in page coordinates."""
    remarks: list[str] = []
    counts: Counter = Counter()
    machine = _Interpreter(box, remarks, counts)
    machine.run(data, _State(ctm=ctm or Matrix.IDENTITY, clip=box), resources, ())
    return InterpretedPage(
        number=number,
        box=box,
        shapes=tuple(machine.shapes),
        remarks=tuple(remarks),
        counts=counts,
    )


def page_content(page) -> bytes:
    """The page's content stream, whether it is one stream or an array of them.

    Both forms occur in files this tool will be pointed at; `HANDOFF.md`
    records finding both in the first PDF it looked at.
    """
    contents = _entry(page, "Contents")
    if contents is None:
        return b""
    if isinstance(contents, list):
        parts = []
        for item in contents:
            try:
                parts.append(_resolve(item).get_data())
            except Exception:
                continue
        return b"\n".join(parts)
    try:
        return contents.get_data()
    except Exception:
        return b""


def page_box(page) -> Rect:
    """The page's visible area: its CropBox where it has one, else MediaBox."""
    for key in ("CropBox", "MediaBox"):
        raw = _entry(page, key)
        if raw is None:
            continue
        values = _numbers(list(_resolve(raw)))
        if values and len(values) >= 4:
            return Rect.from_points([(values[0], values[1]), (values[2], values[3])])
    return Rect(0, 0, 612, 792)


def interpret_page(page, number: int = 1) -> InterpretedPage:
    """Interpret a pypdf page object."""
    data = page_content(page)
    result = interpret_stream(
        data,
        box=page_box(page),
        resources=_entry(page, "Resources"),
        number=number,
    )
    if not data:
        result.remarks = result.remarks + (
            "this page has no content stream, so there was nothing to interpret",
        )
    return result
