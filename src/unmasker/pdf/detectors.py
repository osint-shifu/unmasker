"""Tier 1: what a page shows against what it holds.

Two detectors, both of which the interpreter has made cheap.

**Text under a filled shape.** The reason this project exists. A black bar is
drawn over a name; the name is never removed; every parser can read it.

**Text that is never painted.** Render mode 3 puts glyphs in the file that no
renderer draws - selectable, searchable, invisible. A real technique, and free
once the interpreter tracks `Tr`.

## What decides coverage, and what deliberately does not

**Painting order.** A rectangle drawn *before* a piece of text is a background
and hides nothing; the same rectangle drawn after it is a redaction. Nothing
else in the file distinguishes the two, which is why the interpreter stamps an
order on everything it emits.

**Alpha.** A shape at zero alpha paints nothing. Calling it a redaction would
be reporting a finding that is not there.

**Size.** A page-sized fill is the background. `filetrail`'s lesson about
context: the shape alone cannot say what it is, but its size against the page
can.

**Not colour.** A white fill over black text hides it exactly as well as a
black one. Colour decides what the *report* says a human sees, never whether
the text is covered.

## Per character, not per run

A bar that covers half a line is a finding about half a line. Reporting the
whole run whenever any part of it was touched would overstate every partial
redaction in the same direction, and the first document where a reader can see
the page would show them the tool exaggerating. `tests/specimens/pdf/
libreoffice-writer-partial-bars.pdf` exists to hold this honest, and the words
it covers were settled by poppler rather than by anything here.
"""

from __future__ import annotations

from ..findings import Basis, Finding, Location
from .geometry import Colour, Rect
from .interpreter import Glyph, InterpretedPage, Shape, TextRun

# How much of a glyph a shape must cover before the glyph counts as hidden.
# A rule drawn along a line of text clips its descenders; that is a rule, not a
# redaction, and reporting it would bury the real findings in noise.
COVERAGE = 0.55

# Render modes that put ink on the page. 3 is invisible, 7 is clip-only.
PAINTING_MODES = frozenset({0, 1, 2, 4, 5, 6})


def _covers(shape: Shape, page: Rect) -> bool:
    """Whether this shape could hide anything under it."""
    if shape.kind not in ("fill", "image"):
        return False
    if not shape.is_opaque:
        return False
    return not shape.visible_bbox.covers_most_of(page)


def _hidden(glyph: Glyph, box: Rect) -> bool:
    if glyph.bbox.area <= 0:
        return box.contains(glyph.bbox.x0, glyph.bbox.y0)
    return glyph.bbox.intersect(box).area >= glyph.bbox.area * COVERAGE


def _appearance(colour: Colour | None) -> tuple[str, str]:
    """The block to draw for this fill, and what to call it in words."""
    if colour is None:
        return "▒", "a shape whose colour this file does not state plainly"
    if colour.luminance < 0.25:
        return "█", "a black shape"
    if colour.luminance > 0.85:
        # Nothing is visible at all: white on white leaves a blank, and drawing
        # a bar there would describe a page that does not exist.
        return " ", "a white shape"
    return "▓", f"a shape of luminance {colour.luminance:.2f}"


def _lines(page: InterpretedPage) -> list[list[tuple[Glyph, TextRun]]]:
    """Every painted glyph on the page, gathered into lines and ordered.

    Grouping has to happen here and not per show-operation, because producers
    disagree wildly about how much text one operation carries. LibreOffice
    writes a few words at a time; Chrome writes **one glyph per `Tj`**, so a
    detector that reported per run would turn one black bar into eighty-seven
    findings on the same document LibreOffice reported as four.

    Lines are bucketed by the bottom of the glyph box, rounded to the point.
    That is exact for horizontal text and wrong for rotated text, which no
    specimen yet contains - see `tests/specimens/README.md`.
    """
    buckets: dict[int, list[tuple[Glyph, TextRun]]] = {}
    for run in page.texts:
        if run.render_mode not in PAINTING_MODES:
            continue
        for glyph in run.glyphs:
            buckets.setdefault(round(glyph.bbox.y0), []).append((glyph, run))
    return [
        sorted(entries, key=lambda pair: pair[0].bbox.x0)
        for _, entries in sorted(buckets.items(), reverse=True)
    ]


def _readable(text: str) -> str:
    """Whitespace collapsed to single spaces, for the line-context note.

    The padding that lines up a column can be a dozen no-break spaces, and
    printing them - as `repr` does, one `\xa0` at a time - buries the words
    that were supposed to help a reader find the line.
    """
    return " ".join(text.split())


def _spans(glyphs: list[Glyph], covered: list[bool]) -> list[tuple[int, int]]:
    """Maximal runs of covered glyphs, as (start, stop) indices."""
    out, start = [], None
    for i, flag in enumerate(covered):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(covered)))
    return out


def covered_text(page: InterpretedPage) -> list[Finding]:
    """Every place a shape is painted over text that is still in the file."""
    shapes = [s for s in page.shapes if _covers(s, page.box)]
    if not shapes:
        return []

    lines = _lines(page)
    placed: list[tuple[float, float, Finding]] = []

    for shape in shapes:
        box = shape.visible_bbox
        block, described = _appearance(shape.colour)

        for line in lines:
            glyphs = [g for g, _ in line]
            flags = [
                # Painted before the shape, so the shape is on top of it. Text
                # drawn afterwards sits above the bar and is perfectly legible.
                run.order <= shape.order and _hidden(glyph, box)
                for glyph, run in line
            ]
            if not any(flags):
                continue
            estimated = any(run.widths_estimated for _, run in line)

            for start, stop in _spans(glyphs, flags):
                # A covered space at either edge of the span is the bar's
                # padding, not something that was hidden. Trimming it keeps the
                # character count honest about what was concealed; spaces
                # *inside* the span stay, because they are part of the value.
                while start < stop and not glyphs[start].char.strip():
                    start += 1
                while stop > start and not glyphs[stop - 1].char.strip():
                    stop -= 1
                text = "".join(g.char for g in glyphs[start:stop])
                if not text.strip():
                    continue
                covered_box = Rect.from_points(
                    [(g.bbox.x0, g.bbox.y0) for g in glyphs[start:stop]]
                    + [(g.bbox.x1, g.bbox.y1) for g in glyphs[start:stop]]
                )
                placed.append(
                    (
                        covered_box.y1,
                        covered_box.x0,
                        _finding(
                            shape, estimated, glyphs, start, stop, text, block, described, page
                        ),
                    )
                )

    # Reading order: down the page, then across. Position, never strength -
    # nothing here ranks one bar against another.
    placed.sort(key=lambda item: (-item[0], item[1]))
    return [finding for _, _, finding in placed]


def _finding(shape, estimated, glyphs, start, stop, text, block, described, page) -> Finding:
    rest = "".join(g.char for g in glyphs[:start]) + "".join(g.char for g in glyphs[stop:])

    where = (
        f"x {shape.visible_bbox.x0:.1f}-{shape.visible_bbox.x1:.1f}, "
        f"y {shape.visible_bbox.y0:.1f}-{shape.visible_bbox.y1:.1f}"
    )
    summary = f"{len(text)} characters under {described} at {where}"
    if rest.strip():
        summary += f'; the rest of the line still reads "{_readable(rest)}"'
    if estimated:
        summary += (
            "; this font declares no widths, so the extent of its text is an "
            "estimate and the edges of this span may be off by a character"
        )

    return Finding(
        detector="covered-text",
        basis=Basis.DIRECT,
        summary=summary,
        human_sees=block * len(text),
        machine_reads=text,
        location=Location(page=page.number),
        codepoints=tuple(f"U+{ord(c):04X}" for c in text),
    )


def invisible_text(page: InterpretedPage) -> list[Finding]:
    """Text drawn in a render mode that puts no ink on the page.

    Mode 3 is `neither fill nor stroke`; mode 7 adds the glyphs to the clipping
    path and paints nothing. Both leave the text selectable, searchable and
    entirely absent from the page a person looks at.
    """
    findings = []
    for run in page.texts:
        if run.render_mode in PAINTING_MODES:
            continue
        if not run.text.strip():
            continue
        findings.append(
            Finding(
                detector="invisible-text",
                basis=Basis.DIRECT,
                summary=(
                    f"{len(run.text)} characters drawn in render mode "
                    f"{run.render_mode}, which paints nothing"
                ),
                human_sees="",
                machine_reads=run.text,
                location=Location(page=page.number),
                codepoints=tuple(f"U+{ord(c):04X}" for c in run.text),
            )
        )
    return findings


def detect(page: InterpretedPage) -> list[Finding]:
    """Every tier-1 finding on one interpreted page.

    Additive, and nothing here ranks one against another: a page can have a bar
    over its text *and* an invisible run, and those are two findings.
    """
    return covered_text(page) + invisible_text(page)
