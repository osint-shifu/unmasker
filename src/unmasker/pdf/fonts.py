"""Font metrics: how wide a glyph is, and which character it is.

## The line this module walks

`HANDOFF.md` is explicit: **do not write a font decoder.** The specimens prove
why - their text is written `<010203040506>`, a subset font with an encoding
invented by the producer, and resolving that from the glyph program is months of
work for a result pypdf already has.

So decoding is asked of pypdf. What is done here is the arithmetic pypdf does
not expose: the *width* of each glyph, which is what turns "the text starts
here" into "the text occupies this rectangle". Without it a bar covering half a
line cannot be told from one covering all of it, and the tool would report the
whole line as hidden whenever any part of it was.

A width table is a lookup, not a decoder. The file states it, in `/Widths` for a
simple font or `/W` for a CID font, and reading it is no more interpretation
than reading a page number.

## Both tables, because both specimens use one each

LibreOffice writes simple TrueType fonts: `/FirstChar` plus a `/Widths` array,
one byte per code. Chrome writes Type0 fonts: `/W` with two different entry
forms, a `/DW` default, and Identity-H, two bytes per code. A module tested
against one of them handles half the PDFs in the world, and the half it fails
on it fails silently - every extent slightly wrong, no error anywhere.

## When the file does not say

`width_source` and `text_source` record where each answer came from, including
`"none"`. A guessed width is a guessed rectangle, and a guessed rectangle would
let the tool claim a bar covers text it may not touch. The report is required to
carry that admission rather than bury it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Used only when the file supplies no descriptor. Roughly Times' proportions;
# stated here so a reader of a report can see what was assumed.
DEFAULT_ASCENT = 0.75
DEFAULT_DESCENT = -0.25
DEFAULT_WIDTH = 0.5


def _resolve(obj):
    getter = getattr(obj, "get_object", None)
    return getter() if callable(getter) else obj


def _entry(mapping, key):
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


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class FontMetrics:
    """Everything about a font that placing and reading its glyphs needs."""

    name: str | None = None
    subtype: str | None = None
    widths: dict[int, float] = field(default_factory=dict)
    default_width: float = DEFAULT_WIDTH
    bytes_per_code: int = 1
    chars: dict[int, str] = field(default_factory=dict)
    ascent: float = DEFAULT_ASCENT
    descent: float = DEFAULT_DESCENT

    width_source: str = "none"
    """`Widths`, `W`, or `none`. Named in the report when it is `none`, because
    every extent from such a font is an estimate and saying so is the
    difference between evidence and a guess."""

    text_source: str = "none"
    """`pypdf`, or `none` when the font offered no way to read its codes."""

    def codes(self, raw: bytes) -> list[int]:
        """Split a show-string into character codes.

        A trailing odd byte in a two-byte encoding is kept as its own code
        rather than dropped: it is damage, and dropping it would silently
        shorten the run's extent.
        """
        if self.bytes_per_code == 2:
            out = [int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw) - 1, 2)]
            if len(raw) % 2:
                out.append(raw[-1])
            return out
        return list(raw)

    def advance(self, code: int) -> float:
        """The glyph's width, as a fraction of the em."""
        return self.widths.get(code, self.default_width)

    def char(self, code: int) -> str:
        """The character, or `""` when the font gave no way to know.

        Empty rather than a placeholder: a wrong character in the `machine
        reads` column would be the tool inventing evidence.
        """
        return self.chars.get(code, "")

    @property
    def widths_are_estimated(self) -> bool:
        return self.width_source == "none"


def _simple_widths(font) -> tuple[dict[int, float], str]:
    first = _number(_entry(font, "FirstChar"))
    raw = _entry(font, "Widths")
    if first is None or not raw:
        return {}, "none"
    table: dict[int, float] = {}
    for offset, value in enumerate(raw):
        width = _number(_resolve(value))
        if width is not None:
            table[int(first) + offset] = width / 1000.0
    return (table, "Widths") if table else ({}, "none")


def _cid_widths(descendant) -> tuple[dict[int, float], str]:
    """Parse `/W`, which has two entry forms and mixes them freely.

    c [w1 w2 …]      codes c, c+1, … take w1, w2, …
    c_first c_last w every code in the range takes w
    """
    raw = _entry(descendant, "W")
    if not raw:
        return {}, "none"
    items = [_resolve(v) for v in raw]
    table: dict[int, float] = {}
    i = 0
    while i < len(items):
        start = _number(items[i])
        if start is None:
            i += 1
            continue
        if i + 1 < len(items) and isinstance(items[i + 1], (list, tuple)):
            for offset, value in enumerate(_resolve(items[i + 1])):
                width = _number(_resolve(value))
                if width is not None:
                    table[int(start) + offset] = width / 1000.0
            i += 2
        elif i + 2 < len(items):
            last = _number(items[i + 1])
            width = _number(items[i + 2])
            if last is not None and width is not None:
                # A pathological range would allocate for ever; CIDs stop at
                # 65535 and anything wider than that is damage, not a font.
                for code in range(int(start), min(int(last), 65535) + 1):
                    table[code] = width / 1000.0
            i += 3
        else:
            break
    return (table, "W") if table else ({}, "none")


def _descriptor_metrics(descriptor) -> tuple[float, float]:
    ascent = _number(_entry(descriptor, "Ascent"))
    descent = _number(_entry(descriptor, "Descent"))
    bbox = _entry(descriptor, "FontBBox")
    if (ascent is None or descent is None) and bbox and len(bbox) >= 4:
        # A descriptor without Ascent still has a bounding box, and its top and
        # bottom are the same measurement by another name.
        descent = descent if descent is not None else _number(_resolve(bbox[1]))
        ascent = ascent if ascent is not None else _number(_resolve(bbox[3]))
    return (
        (ascent / 1000.0) if ascent is not None else DEFAULT_ASCENT,
        (descent / 1000.0) if descent is not None else DEFAULT_DESCENT,
    )


def _char_map(font) -> tuple[dict[int, str], str]:
    """Ask pypdf to decode this font's codes.

    Kept in one place, and wrapped, so that the day pypdf moves this the tool
    reports positions without text and says so, rather than failing to read the
    page at all.
    """
    if font is None:
        return {}, "none"
    try:
        from pypdf._cmap import get_encoding

        _, mapping = get_encoding(font)
    except Exception:
        return {}, "none"
    table: dict[int, str] = {}
    for key, value in (mapping or {}).items():
        if isinstance(key, str) and len(key) == 1 and isinstance(value, str):
            table[ord(key)] = value
        elif isinstance(key, int) and isinstance(value, str):
            table[key] = value
    return (table, "pypdf") if table else ({}, "none")


def load_font(font, name: str | None = None) -> FontMetrics:
    """Read everything needed to place and read one font's glyphs.

    `font` may be None - a `Tf` naming a resource that is not there. That must
    not stop the page being read, so it produces usable defaults whose
    `width_source` says they are defaults.
    """
    if font is None:
        return FontMetrics(name=name)

    subtype = _entry(font, "Subtype")
    subtype = str(subtype).lstrip("/") if subtype is not None else None
    chars, text_source = _char_map(font)

    if subtype == "Type0":
        encoding = str(_entry(font, "Encoding") or "")
        # Identity-H and Identity-V are two bytes per code. Every other CMap
        # this is likely to meet is too; a one-byte CMap exists but is rare
        # enough that guessing two is the better default, and the run's text
        # would visibly disagree if it were wrong.
        bytes_per_code = 1 if encoding.endswith("Identity-B") else 2
        descendants = _entry(font, "DescendantFonts")
        descendant = _resolve(descendants[0]) if descendants else None
        widths, source = _cid_widths(descendant)
        default = _number(_entry(descendant, "DW"))
        ascent, descent = _descriptor_metrics(_entry(descendant, "FontDescriptor"))
        return FontMetrics(
            name=name,
            subtype=subtype,
            widths=widths,
            default_width=(default / 1000.0) if default is not None else 1.0,
            bytes_per_code=bytes_per_code,
            chars=chars,
            ascent=ascent,
            descent=descent,
            width_source=source,
            text_source=text_source,
        )

    widths, source = _simple_widths(font)
    descriptor = _entry(font, "FontDescriptor")
    ascent, descent = _descriptor_metrics(descriptor)
    missing = _number(_entry(descriptor, "MissingWidth"))
    return FontMetrics(
        name=name,
        subtype=subtype,
        widths=widths,
        default_width=(missing / 1000.0) if missing is not None else DEFAULT_WIDTH,
        bytes_per_code=1,
        chars=chars,
        ascent=ascent,
        descent=descent,
        width_source=source,
        text_source=text_source,
    )
