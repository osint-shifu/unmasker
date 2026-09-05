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

import math

from ..findings import Basis, Finding, Location
from .geometry import WHITE, Colour, Rect
from .interpreter import Glyph, InterpretedPage, Shape, TextRun
from .rendered import CONFIDENT, UNREAD_RUN, ReadWord

# How much of a glyph a shape must cover before the glyph counts as hidden.
# A rule drawn along a line of text clips its descenders; that is a rule, not a
# redaction, and reporting it would bury the real findings in noise.
COVERAGE = 0.55

# Render modes that put ink on the page. 3 is invisible, 7 is clip-only.
PAINTING_MODES = frozenset({0, 1, 2, 4, 5, 6})

# Alpha at or below which paint puts nothing perceptible on the page, and the
# alpha below which it is faint enough that a reader may miss it. The second is
# also how a watermark is set, so it is reported with a weaker basis.
INVISIBLE_ALPHA = 0.01
FAINT_ALPHA = 0.15
STROKE_ONLY_MODES = frozenset({1, 5})

# How close two colours have to be before the text stops being readable. Chosen
# to catch #f8f8f8 on white, which no eye resolves, and to leave #e0e0e0 alone,
# which is a legible light grey. The measured difference goes in the summary
# either way, so a reader who would draw the line elsewhere can see where it
# actually fell.
CONTRAST = 0.08
EXACT = 0.005


def _count(text: str) -> str:
    """`1 character`, not `1 characters`. A report is read by a person."""
    return f"{len(text)} character" + ("" if len(text) == 1 else "s")


def _covers(shape: Shape, page: Rect, kinds: tuple[str, ...] = ("fill",)) -> bool:
    """Whether this shape could hide anything under it."""
    if shape.kind not in kinds:
        return False
    if not shape.is_opaque:
        return False
    return not shape.visible_bbox.covers_most_of(page)


def _hidden(glyph: Glyph, box: Rect) -> bool:
    if glyph.bbox.area <= 0:
        return box.contains(glyph.bbox.x0, glyph.bbox.y0)
    return glyph.bbox.intersect(box).area >= glyph.bbox.area * COVERAGE


def _appearance(shape: Shape) -> tuple[str, str]:
    """The block to draw for this shape, and what to call it in words."""
    if shape.kind == "image":
        return "▒", "an image"
    colour = shape.colour
    if colour is None:
        return "▒", "a shape whose colour this file does not state plainly"
    if colour.luminance < 0.25:
        return "█", "a black shape"
    if colour.luminance > 0.85:
        # Nothing is visible at all: white on white leaves a blank, and drawing
        # a bar there would describe a page that does not exist.
        return " ", "a white shape"
    return "▓", f"a shape of luminance {colour.luminance:.2f}"


def _painted(run: TextRun) -> bool:
    return run.render_mode in PAINTING_MODES and not run.is_invisible


def _angle_of(run: TextRun) -> float:
    """The angle this run's text advances at, in degrees."""
    dx, dy = run.direction
    return math.degrees(math.atan2(dy, dx))


def _lines(page: InterpretedPage, include=_painted) -> list[list[tuple[Glyph, TextRun]]]:
    """Every painted glyph on the page, gathered into lines and ordered.

    Grouping has to happen here and not per show-operation, because producers
    disagree wildly about how much text one operation carries. LibreOffice
    writes a few words at a time; Chrome writes **one glyph per `Tj`**, so a
    detector that reported per run would turn one black bar into eighty-seven
    findings on the same document LibreOffice reported as four.

    A line is glyphs that share an angle and sit at the same distance across
    it, ordered by how far along it they are. Three things follow from stating
    it that way rather than as "the same bottom edge, sorted left to right":

    **A rotated line is one line.** Turn text ninety degrees and every glyph
    has a different bottom edge and the same left edge, so the old rule
    reported one hidden line as one finding per letter - measured at fifteen
    on `libreoffice-calc-rotated-headers.pdf`. It is the same failure Chrome's
    one-glyph-per-`Tj` produced, arriving from a different direction.

    **The angle is part of the key**, so a rotated header and a horizontal cell
    that happen to sit at the same height never merge into a line that exists
    nowhere on the page.

    **Position comes from the glyph's origin, not its box.** The origin is on
    the baseline, so a superscript stays on the line it belongs to; the box's
    bottom edge is the descent, which a smaller font puts somewhere else.
    """
    buckets: dict[tuple[int, int], list[tuple[Glyph, TextRun]]] = {}
    for run in page.texts:
        if not include(run):
            continue
        dx, dy = run.direction
        angle = round(_angle_of(run))
        for glyph in run.glyphs:
            x, y = glyph.origin
            # Distance across the line: the origin projected onto the
            # perpendicular. For horizontal text this is exactly the baseline
            # height, which is what it used to be.
            buckets.setdefault((angle, round(-x * dy + y * dx)), []).append((glyph, run))

    def along(pair: tuple[Glyph, TextRun]) -> float:
        glyph, run = pair
        return glyph.origin[0] * run.direction[0] + glyph.origin[1] * run.direction[1]

    return [sorted(entries, key=along) for _, entries in sorted(buckets.items(), reverse=True)]


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
    return _under(page, ("fill",), "covered-text")


def text_under_image(page: InterpretedPage) -> list[Finding]:
    """Text with an image painted over it.

    Split from `covered_text` because the innocent explanation is different and
    common: a scanned page carries an image of the paper with a text layer
    beneath it, and the two normally say the same thing. That is still a gap
    between what a reader sees and what a parser gets, so it is reported - but
    the report names the explanation instead of implying a motive.

    A page-sized image is excluded before this by the size rule, so the whole
    scanned-page case does not reach here at all; what does is a smaller image
    placed over text, which is a different act.
    """
    return _under(page, ("image",), "text-under-image")


def _under(page: InterpretedPage, kinds: tuple[str, ...], detector: str) -> list[Finding]:
    shapes = [s for s in page.shapes if _covers(s, page.box, kinds)]
    if not shapes:
        return []

    lines = _lines(page)
    placed: list[tuple[float, float, Finding]] = []

    for shape in shapes:
        box = shape.visible_bbox
        block, described = _appearance(shape)

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
                            shape,
                            estimated,
                            glyphs,
                            start,
                            stop,
                            text,
                            block,
                            described,
                            page,
                            detector,
                        ),
                    )
                )

    # Reading order: down the page, then across. Position, never strength -
    # nothing here ranks one bar against another.
    placed.sort(key=lambda item: (-item[0], item[1]))
    return [finding for _, _, finding in placed]


def _finding(
    shape, estimated, glyphs, start, stop, text, block, described, page, detector
) -> Finding:
    rest = "".join(g.char for g in glyphs[:start]) + "".join(g.char for g in glyphs[stop:])

    where = (
        f"x {shape.visible_bbox.x0:.1f}-{shape.visible_bbox.x1:.1f}, "
        f"y {shape.visible_bbox.y0:.1f}-{shape.visible_bbox.y1:.1f}"
    )
    summary = f"{_count(text)} under {described} at {where}"
    if shape.kind == "image":
        summary += (
            "; an image over a text layer is also what a scan of a printed page "
            "looks like, and there the two normally agree"
        )
    if rest.strip():
        summary += f'; the rest of the line still reads "{_readable(rest)}"'
    if estimated:
        summary += (
            "; this font declares no widths, so the extent of its text is an "
            "estimate and the edges of this span may be off by a character"
        )

    return Finding(
        detector=detector,
        basis=Basis.DIRECT,
        summary=summary,
        human_sees=block * len(text),
        machine_reads=text,
        location=Location(page=page.number),
        codepoints=tuple(f"U+{ord(c):04X}" for c in text),
    )


def _why_invisible(run: TextRun) -> tuple[str, str] | None:
    """(kind, wording) for a run that puts nothing on the page, else None."""
    if run.render_mode not in PAINTING_MODES:
        return (
            f"mode-{run.render_mode}",
            f"drawn in render mode {run.render_mode}, which paints neither fill nor stroke",
        )
    if run.alpha <= INVISIBLE_ALPHA:
        return (
            "clear",
            f"painted at an opacity of {run.alpha:g}, which puts nothing on the "
            "page; the glyphs are laid out and shaped as any others",
        )
    if run.alpha <= FAINT_ALPHA:
        return (
            "faint",
            f"painted at an opacity of {run.alpha:g}, faint enough that a reader "
            "may not see it - and also how a watermark is set",
        )
    return None


def invisible_text(page: InterpretedPage) -> list[Finding]:
    """Text that puts nothing on the page: by its render mode or its opacity.

    Mode 3 is `neither fill nor stroke` and mode 7 adds the glyphs to the
    clipping path; an OCR layer under a scanned page is written in one of them,
    by every OCR pipeline there is. Zero opacity is the same statement made a
    different way, and `color: transparent` is one CSS declaration.

    Grouped by line, not by show-operation. tesseract writes one operation per
    *word*, so reporting per run turns one hidden line into eight findings -
    the same mistake `covered_text` made with Chrome, which writes one per
    glyph, and the same fix.
    """
    lines = _lines(page, include=lambda run: _why_invisible(run) is not None)
    findings = []
    for line in lines:
        # A line could in principle mix an unpainted run with a transparent
        # one. They are different statements, so they stay different findings.
        by_kind: dict[str, list[tuple[Glyph, TextRun]]] = {}
        for glyph, run in line:
            reason = _why_invisible(run)
            if reason is None:
                continue  # filtered out by _lines() above; re-stated for the checker
            by_kind.setdefault(reason[0], []).append((glyph, run))

        for entries in by_kind.values():
            text = _joined(entries)
            if not text.strip():
                continue
            run = entries[0][1]
            reason = _why_invisible(run)
            if reason is None:
                continue
            kind, why = reason
            findings.append(
                Finding(
                    detector="invisible-text",
                    basis=(Basis.CIRCUMSTANTIAL if kind == "faint" else Basis.DIRECT),
                    summary=f"{_count(text)} {why}",
                    human_sees="",
                    machine_reads=text,
                    location=Location(page=page.number),
                    codepoints=tuple(f"U+{ord(c):04X}" for c in text),
                )
            )
    return findings


def _joined(entries: list[tuple[Glyph, TextRun]]) -> str:
    """The glyphs of a line, with a space wherever the pen jumped a gap.

    A producer that writes one show-operation per word emits no space between
    them - the gap is in the positioning. Joining the glyphs without putting it
    back would report `Agreedfigure:250,000EUR`, which is not what any parser
    reads out of the file.
    """
    out: list[str] = []
    previous = None
    for glyph, run in entries:
        if previous is not None:
            gap = glyph.bbox.x0 - previous.bbox.x1
            if gap > run.size * 0.15 and not out[-1].isspace():
                out.append(" ")
        out.append(glyph.char)
        previous = glyph
    return "".join(out)


def _normalise(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


# How large a gap between two glyphs on a line ends a word, as a fraction of
# the font size. A typeset space is about a quarter of an em and letter-spacing
# is near zero, so anything in between separates them.
#
# Unlike `UNREAD_RUN`, this is **chosen and not measured**: no specimen here
# exercises it, because every producer on this machine emits space characters
# and the whitespace rule fires first. It is defence against one that does not
# - some generators position each word with `Td` and write no spaces at all -
# and `test_a_gap_wide_enough_to_be_a_space_breaks_a_word` is the only thing
# that holds it.
WORD_GAP = 0.20


def _words_of(page: InterpretedPage, painted_only: bool = True) -> list[list[Glyph]]:
    """Glyphs grouped into words, across show-operations and along the line.

    `painted_only` decides which question is being asked. For *is this in the
    file and not on the page*, only painted text counts - text a render mode
    never draws is legitimately absent from the picture and `invisible_text`
    has already said so. For *is this on the page and not in the file*, every
    run counts, painted or not: an invisible OCR layer is still text in the
    file, and `pdftotext` reads it straight out.

    **Words are counted across runs, and the reason is a threshold.** The OCR
    detectors report a run of consecutive unread *words*, and `UNREAD_RUN` was
    measured against the specimens as the line between the control and every
    file that hides something. That measurement means nothing if a word is
    sometimes a letter - and Chrome writes one glyph per `Tj`, so grouping
    inside each run turned one page's 62 words into 353. Five unread words
    became five unread letters, a far lower bar than the one measured.

    The fifth place this project has found the same rule broken, after
    `covered_text`, `invisible_text`, `low_contrast_text` and `off_page_text`.

    Poppler settles the count, not this code: `pdftotext FILE - | wc -w` on
    four specimens, asserted in `tests/test_ocr.py`.
    """

    def wanted(run: TextRun) -> bool:
        return not painted_only or (run.render_mode in PAINTING_MODES and not run.is_invisible)

    out: list[list[Glyph]] = []
    for line in _lines(page, include=wanted):
        current: list[Glyph] = []
        end: float | None = None
        for glyph, run in line:
            dx, dy = run.direction
            start = glyph.origin[0] * dx + glyph.origin[1] * dy
            extent = abs(glyph.bbox.width * dx) + abs(glyph.bbox.height * dy)

            breaks = not glyph.char.strip() or (
                end is not None and start - end > WORD_GAP * run.size
            )
            if breaks and current:
                out.append(current)
                current = []
            if glyph.char.strip():
                current.append(glyph)
            end = start + extent
        if current:
            out.append(current)
    return out


def _box_of(glyphs: list[Glyph]) -> Rect:
    return Rect.from_points(
        [(g.bbox.x0, g.bbox.y0) for g in glyphs] + [(g.bbox.x1, g.bbox.y1) for g in glyphs]
    )


def unrendered_text(page: InterpretedPage, read: list[ReadWord]) -> list[Finding]:
    """Words the file holds that the picture of the page does not show.

    This is the one detector that knows no technique. It does not care whether
    the words are under a bar, painted at no opacity, in the colour of the
    paper or off the edge of it - only that they are in the file and not on the
    page. A method nobody here has thought of still fails that question, which
    is the only kind of check that can catch one.

    It also cannot be certain, ever. OCR is wrong constantly and its being
    wrong looks exactly like concealment, which is why a run has to be
    `UNREAD_RUN` words long before it is reported and why the basis is always
    circumstantial. The threshold is measured rather than chosen: see
    `rendered.py`.
    """
    if not read:
        return []

    findings: list[Finding] = []
    span: list[list[Glyph]] = []

    def flush() -> None:
        if len(span) < UNREAD_RUN:
            span.clear()
            return
        text = " ".join("".join(g.char for g in word) for word in span)
        box = _box_of([g for word in span for g in word])
        findings.append(
            Finding(
                detector="unrendered-text",
                basis=Basis.CIRCUMSTANTIAL,
                summary=(
                    f"{len(span)} consecutive words at x {box.x0:.1f}-{box.x1:.1f}, "
                    f"y {box.y0:.1f}-{box.y1:.1f} are in the file and were not read "
                    "back off a rendering of the page. Nothing here knows how they "
                    "are hidden, only that they are - and OCR failing to read text "
                    "looks the same as text not being there"
                ),
                human_sees="",
                machine_reads=text,
                location=Location(page=page.number),
            )
        )
        span.clear()

    for word in _words_of(page):
        wanted = _normalise("".join(g.char for g in word))
        if not wanted:
            continue
        box = _box_of(word)
        nearby = "".join(_normalise(w.text) for w in read if not box.intersect(w.bbox).is_empty)
        if wanted in nearby:
            flush()
        else:
            span.append(word)
    flush()
    return findings


def unextractable_text(page: InterpretedPage, read: list[ReadWord]) -> list[Finding]:
    """Words the page shows that the file does not hold.

    The gap the other way round, and the question this project has declined to
    answer since its first specimen: a page with no text layer could be read
    only by rendering it, and now it can be.

    Only confident readings count. Claiming the page shows something the file
    lacks on the strength of a low-confidence guess would be inventing the
    evidence rather than reading it.
    """
    if not read:
        return []

    boxes = [_box_of(word) for word in _words_of(page, painted_only=False)]
    orphans = [
        w
        for w in read
        if w.confidence >= CONFIDENT
        and _normalise(w.text)
        and not any(not w.bbox.intersect(b).is_empty for b in boxes)
    ]
    if len(orphans) < UNREAD_RUN:
        return []

    text = " ".join(w.text for w in orphans)
    box = Rect.from_points(
        [(w.bbox.x0, w.bbox.y0) for w in orphans] + [(w.bbox.x1, w.bbox.y1) for w in orphans]
    )
    return [
        Finding(
            detector="unextractable-text",
            basis=Basis.CIRCUMSTANTIAL,
            summary=(
                f"{len(orphans)} words were read off a rendering of the page and "
                "have no text in the file underneath them. The page shows them and "
                "no parser gets them; this is what a scan without an OCR layer "
                "looks like, and the words below are this tool's reading of the "
                f"picture rather than anything the file says (x {box.x0:.1f}-"
                f"{box.x1:.1f}, y {box.y0:.1f}-{box.y1:.1f})"
            ),
            human_sees=text,
            machine_reads="",
            location=Location(page=page.number),
        )
    ]


def annotation_text(page: InterpretedPage) -> list[Finding]:
    """Comments and notes attached to the page but not part of it.

    Same statement as a DOCX comment and the same detector name, arriving
    through a wholly different mechanism: there, a part of a zip the
    application agrees not to display; here, a dictionary hanging off the page.
    """
    findings = []
    for note in page.annotations:
        if not note.is_a_note:
            continue
        who = f" by {note.author}" if note.author else ""
        findings.append(
            Finding(
                detector="comment",
                basis=Basis.DIRECT,
                summary=(
                    f"a /{note.subtype} annotation{who}, attached to the page "
                    "and not part of it; it does not print and text extraction "
                    "does not report it"
                ),
                human_sees="",
                machine_reads=note.contents,
                location=Location(page=page.number),
            )
        )
    return findings


def remarks(page: InterpretedPage) -> list[str]:
    """What this page's detectors could not establish, as opposed to found.

    `CONTRIBUTING.md`: "nothing found" has two meanings, and a reader who cannot tell
    them apart has been told something the tool never established. Silence
    about text sitting on a picture is one of the two: whether those glyphs are
    legible depends on what colour the picture is exactly where they sit, and
    the content stream does not say. Nothing short of rendering it finds out.
    """
    on_a_picture = 0
    for run in page.texts:
        if run.render_mode not in PAINTING_MODES or run.is_invisible:
            continue
        for glyph in run.glyphs:
            if not glyph.char.strip():
                continue
            if _background(page, glyph, run) is None:
                on_a_picture += 1

    painted_notes = sum(
        1 for note in page.annotations if note.has_appearance and note.subtype != "Popup"
    )
    extra = (
        [
            f"page {page.number} has {painted_notes} annotation(s) carrying an "
            "appearance stream; what those paint is not interpreted, so anything "
            "one of them covers was not checked"
        ]
        if painted_notes
        else []
    )

    if not on_a_picture:
        return extra
    return extra + [
        f"page {page.number} has {_count('x' * on_a_picture)} sitting on a "
        "picture or on a fill this file does not state plainly; whether they "
        "can be read there was not established, because what colour it is "
        "where they sit is not in the content stream"
    ]


def detect(page: InterpretedPage) -> list[Finding]:
    """Every tier-1 finding on one interpreted page.

    Additive, and nothing here ranks one against another: a page can have a bar
    over its text *and* an invisible run, and those are two findings.
    """
    return (
        covered_text(page)
        + text_under_image(page)
        + annotation_text(page)
        + invisible_text(page)
        + low_contrast_text(page)
        + off_page_text(page)
    )


def _background(page: InterpretedPage, glyph: Glyph, run: TextRun) -> Colour | None:
    """The colour the eye sees behind one glyph.

    The topmost opaque shape painted *before* the run and containing the glyph.
    Where there is none the background is the paper, and a PDF has no page
    colour - the paper is white, and white text on nothing is invisible without
    any shape being involved.

    Returns None when a shape is there but its colour is not readable, because
    "we cannot tell what is behind this" and "it is white" are different
    answers and only one of them is true.
    """
    best: Shape | None = None
    for shape in page.shapes:
        if shape.kind not in ("fill", "image") or shape.order >= run.order:
            continue
        if not shape.is_opaque:
            continue
        if not shape.visible_bbox.intersect(glyph.bbox).area >= glyph.bbox.area * COVERAGE:
            continue
        if best is None or shape.order > best.order:
            best = shape
    if best is None:
        return WHITE
    if best.kind == "image":
        # A photograph, a letterhead, a watermark. What colour the picture is
        # where this glyph sits is not something the content stream says, and
        # answering "white, like the paper" would be inventing the evidence
        # rather than reading it.
        return None
    return best.colour


def _ink(run: TextRun) -> Colour | None:
    """The colour this run is painted in, for the mode it is painted in."""
    return run.stroke if run.render_mode in STROKE_ONLY_MODES else run.fill


def _hex(colour: Colour) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in colour.rgb)


def low_contrast_text(page: InterpretedPage) -> list[Finding]:
    """Text painted in the colour of whatever is behind it.

    Nothing is drawn over it; it is simply the same colour as its background,
    which hides it from a reader and from nobody else.

    An exact match is `DIRECT` - the text provably cannot be distinguished. A
    near match is `CIRCUMSTANTIAL`, because a difference this small may still
    be legible on a good screen and because light grey is a legitimate way to
    set a watermark. The measured difference is in the summary either way.

    Grouped by line, like every other detector here. This one was reporting per
    show-operation for longer than the others because LibreOffice writes whole
    words per operation in horizontal text, so nothing showed - until a page of
    *rotated* cells, where it writes one glyph at a time and one hidden line
    came out as fifteen findings. Third time this rule has been broken in a
    different place: `covered_text` had it with Chrome, `invisible_text` had it
    with tesseract.
    """
    findings: list[Finding] = []
    for line in _lines(page):
        glyphs = [glyph for glyph, _ in line]
        runs = [run for _, run in line]
        inks = [_ink(run) for run in runs]
        behind = [_background(page, g, run) for g, run in line]
        gaps = [
            None
            if b is None or ink is None
            else max(abs(x - y) for x, y in zip(ink.rgb, b.rgb, strict=True))
            for ink, b in zip(inks, behind, strict=True)
        ]
        flags = [g is not None and g <= CONTRAST for g in gaps]

        for start, stop in _spans(glyphs, flags):
            text = "".join(g.char for g in glyphs[start:stop])
            if not text.strip():
                continue
            measured = [gap for gap in gaps[start:stop] if gap is not None]
            paper = behind[start]
            ink = inks[start]
            if not measured or paper is None or ink is None:
                continue  # _spans() only yields where all three were present
            worst = max(measured)
            run = runs[start]
            findings.append(
                Finding(
                    detector="low-contrast-text",
                    basis=Basis.DIRECT if worst <= EXACT else Basis.CIRCUMSTANTIAL,
                    summary=(
                        f"{_count(text)} painted {_hex(ink)} on "
                        f"{_hex(paper)}"
                        + (
                            ", the same colour"
                            if worst <= EXACT
                            else f", a difference of {worst:.3f} on the strongest channel"
                        )
                        + (
                            "; nothing is drawn over this text, and the background "
                            "is the paper itself"
                            if _is_paper(page, glyphs[start], run)
                            else "; the background is a shape painted before it"
                        )
                    ),
                    human_sees="",
                    machine_reads=text,
                    location=Location(page=page.number),
                    codepoints=tuple(f"U+{ord(c):04X}" for c in text),
                )
            )
    return findings


def _is_paper(page: InterpretedPage, glyph: Glyph, run: TextRun) -> bool:
    for shape in page.shapes:
        if shape.kind not in ("fill", "image") or shape.order >= run.order:
            continue
        if not shape.is_opaque:
            continue
        if shape.visible_bbox.intersect(glyph.bbox).area >= glyph.bbox.area * COVERAGE:
            return False
    return True


def off_page_text(page: InterpretedPage) -> list[Finding]:
    """Text positioned where no viewer will show it.

    Outside the page box - which is the CropBox where a file has one, and a
    CropBox smaller than the MediaBox is the ordinary way a PDF is trimmed
    without anything being removed - or outside the clip in force when it was
    drawn.

    A glyph counts only when it has *no* overlap at all with the visible area.
    Half a word past a margin is a layout accident, and reporting those would
    make the detector fire on most of the documents it is ever pointed at.

    ## A cell boundary and a redaction are the same mechanism

    Text is drawn, a clip is in force, part of the text falls outside it. One
    of those is a column too narrow for what was typed into it; the other is a
    hidden sentence. Nothing in the file distinguishes them, and a spreadsheet
    exported to PDF can produce a screenful of the first - after which a reader
    scrolls past the second.

    What can be said is what **the rest of the line** supports. Clipped text
    with visible text beside it on the same line is what an overflow looks
    like; a line clipped away entirely is not. So the first is
    `CIRCUMSTANTIAL` and says so in its summary.

    It is not suppressed, and that is the point of using the evidence class
    rather than a filter: a redaction that clips only the second half of a line
    looks exactly like an overflow, and a tool that deleted the finding would
    have decided for its reader.
    """
    findings: list[Finding] = []
    for line in _lines(page, include=lambda run: bool(run.text.strip())):
        glyphs = [glyph for glyph, _ in line]
        areas = [page.box.intersect(run.clip) if run.clip else page.box for _, run in line]
        flags = [
            not glyph.bbox.overlaps(area) for glyph, area in zip(glyphs, areas, strict=True)
        ]
        remainder = "".join(g.char for g, flag in zip(glyphs, flags, strict=True) if not flag)

        for start, stop in _spans(glyphs, flags):
            text = "".join(g.char for g in glyphs[start:stop])
            if not text.strip():
                continue
            box = Rect.from_points(
                [(g.bbox.x0, g.bbox.y0) for g in glyphs[start:stop]]
                + [(g.bbox.x1, g.bbox.y1) for g in glyphs[start:stop]]
            )
            visible = areas[start]
            findings.append(
                Finding(
                    detector="off-page-text",
                    basis=Basis.CIRCUMSTANTIAL if remainder.strip() else Basis.DIRECT,
                    summary=(
                        f"{_count(text)} at x {box.x0:.1f}-{box.x1:.1f}, "
                        f"y {box.y0:.1f}-{box.y1:.1f}, entirely outside the visible "
                        f"area x {visible.x0:.1f}-{visible.x1:.1f}, "
                        f"y {visible.y0:.1f}-{visible.y1:.1f}"
                        + (
                            "; the rest of the line is on the page, so this may be "
                            f"text overflowing its box - {_readable(remainder)!r}"
                            if remainder.strip()
                            else ""
                        )
                    ),
                    human_sees="",
                    machine_reads=text,
                    location=Location(page=page.number),
                    codepoints=tuple(f"U+{ord(c):04X}" for c in text),
                )
            )
    return findings
