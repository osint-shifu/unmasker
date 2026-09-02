"""The screen a bare `unmasker` prints, and the mark it opens with.

Typing a tool's name and getting `error: the following arguments are required`
tells a reader they were wrong and nothing else. A landing screen's job is to
get somebody to their first useful command.

## The mark

    █████ker
    unmasker

A bar dragged too short, and the word still there underneath it. The top line
is what a human sees; the bottom line is what a machine reads; the gap between
them is the entire tool. It needs no caption, it is five characters wide, and
it is the same failed redaction this project exists to report - drawn in the
only two rows a terminal can be relied on to give you.

It is unmasker's own, and deliberately not `filetrail`'s wordmark in a
different font. The two tools share a *design language* - `filetrail`'s
`DESIGN.md`, which `CLAUDE.md` says to read before inventing a second one - and
share the one rule that matters, that **colour encodes how the tool knows and
never how bad the finding is**. What they do not share is an identity. A reader
who has both installed should be able to tell in one glance which one just
printed at them.

## Built out of the report, not beside it

The sections use `report._header` and `report._field`, so the front door cannot
drift from the thing it advertises - and a reader arrives at their first real
report already knowing how to read a `│ label  value` row, because they have
just read four screens of them.

A front door with its own layout code goes stale, and the first person to
notice is one who ran the tool and got something that did not match the box.
"""

from __future__ import annotations

import sys
import textwrap
from typing import TextIO

from . import __version__
from .report import MARGIN, Style, _field, _header, _rule
from .theme import FAINT, FOREGROUND, MUTED

REPOSITORY = "github.com/osint-shifu/unmasker"
TAGLINE = "What a human sees in a document, against what a machine reads out of it."

#: The bar, and what to draw it with where a terminal cannot encode a block.
#: Same rule as `theme.GLYPHS`: the layout never changes, only the characters.
BLOCK = ("█", "#")

#: How much of the word the bar covers. Five of eight - short enough that
#: `ker` escapes, which is the point, and long enough that it reads as a
#: redaction rather than as a typo.
COVERED = 5

#: The number the header prints. Held by a test against the slugs in the
#: source: a landing screen that overstates the tool is the first thing a
#: reader can check, and the first thing to go stale.
DETECTORS = 22

#: Five lines, one per place a document can hide something, in the order the
#: README uses. Not a detector list - a reader looking for their own case
#: recognises it here and finds the name for it in the README.
LOOKS_AT = (
    ("on the page", "a bar over text, the colour of the paper, off the crop box"),
    ("in characters", "zero-width, bidi overrides, tag characters, mixed script"),
    ("in a workbook", "hidden sheets, rows, columns, and cells that were edited"),
    ("in the file", "tracked changes, comments, metadata that contradicts itself"),
    ("by rendering", "--ocr reads the page back, knowing no technique at all"),
)

READS = (
    ("opens", "PDF · DOCX · ODT · XLSX · ODS · text"),
    (
        "refuses",
        ".pptx and .odp, rather than read a deck as prose and report a "
        "hidden slide as visible text",
    ),
)

RUNNING = (
    ("a document", "unmasker leaked.pdf"),
    ("a pipeline", "unmasker leaked.pdf --json"),
    ("the slow way", "unmasker leaked.pdf --ocr    needs ghostscript, tesseract"),
    ("exit status", "0 nothing found · 1 findings exist · 2 could not be read"),
)


def _encodable(text: str, stream: TextIO | None) -> bool:
    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def mark(stream: TextIO | None = None) -> tuple[str, str]:
    """The two lines of the mark: what a human sees, and what a machine reads."""
    rich, plain = BLOCK
    block = rich if _encodable(rich, stream) else plain
    name = "unmasker"
    return block * COVERED + name[COVERED:], name


def _prose(style: Style, text: str, ink) -> list[str]:
    """A paragraph wrapped to the rule the screen has already drawn.

    The masthead must never run past the width it declared - a line that
    overshoots the rule underneath it is the first thing a reader sees, and it
    says the layout was not measured.
    """
    return [
        MARGIN + style.ink(line, ink)
        for line in textwrap.wrap(text, width=style.width - len(MARGIN)) or [""]
    ]


def _rows(style: Style, rows: tuple[tuple[str, str], ...]) -> list[str]:
    """Label and value, sized per section rather than once per screen - one
    global width makes a layout look *almost* aligned, which reads worse than
    not aligning it."""
    width = max(len(label) for label, _ in rows)
    out: list[str] = []
    for label, value in rows:
        out += _field(style, label, value, width)
    return out


def render(style: Style | None = None, stream: TextIO | None = None) -> str:
    style = style or Style()
    covered, underneath = mark(stream)

    version = f"{underneath} {__version__}"
    pad = max(1, style.width - len(MARGIN) - len(version) - len(REPOSITORY))

    out = [
        "",
        # The mark: the bar on one line, the word it failed to cover on the
        # next, aligned so a reader sees the registration rather than two
        # unrelated strings.
        MARGIN + style.ink(covered, FOREGROUND, bold=True),
        MARGIN
        + style.ink(version, FOREGROUND, bold=True)
        + " " * pad
        + style.ink(REPOSITORY, FAINT),
        _rule(style),
    ]
    out += _prose(style, TAGLINE, MUTED)
    out += _prose(
        style,
        "Those two lines are the whole idea: a bar dragged too short, and the "
        "word still in the file underneath it.",
        FAINT,
    )
    out.append("")

    for title, count, rows in (
        ("looks at", f"{DETECTORS} detectors", LOOKS_AT),
        ("reads", "6 formats", READS),
        ("running it", "3 commands, 3 exit codes", RUNNING),
    ):
        out += _header(style, title, count)
        out += _rows(style, rows)
        out.append("")

    out.append(_rule(style))
    out += _prose(
        style,
        "Local, read-only, and it never writes to the file it is given. "
        "unmasker --help for the options.",
        MUTED,
    )
    out.append("")
    return "\n".join(out)
