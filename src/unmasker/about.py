"""The screen a bare `unmasker` prints.

Typing a tool's name and getting `error: the following arguments are required`
tells a reader they were wrong and nothing else. A landing screen's job is to
get somebody to their first useful command, and then get out of the way.

## The mark

    █████ker
    unmasker

A bar dragged too short, and the word still there underneath it. The top line
is what a human sees; the bottom is what a machine reads; the gap between them
is the entire tool. It needs no caption, and it is drawn in the only two rows a
terminal can be relied on to give you.

It is unmasker's own and deliberately not `filetrail`'s wordmark in another
font. The two share a design language and the rule that colour encodes how the
tool knows rather than how bad the finding is. They do not share an identity: a
reader with both installed should never have to wonder which one just printed.

## The shape below it is everybody's

`USAGE`, `OPTIONS`, `EXAMPLES`, `EXIT STATUS` — flush-left capitals, two-space
indent, no rules and no boxes. That is what `gh`, `rg`, `fd` and every other
modern command-line tool prints, and a reader who has used any of them knows
how to read this one in a second. A landing screen exists to get somebody to
the right command, not to be memorable.

Three things follow from that, and each replaced something this file used to
do:

**No prose.** What the tool is for is in `README.md`, where a reader has
scrolling and links. Repeating it here made the first screen a page.

**No rules across the terminal.** The report draws to the width it measured
because its values wrap; a help screen's content is short and fixed, so
stretching it to a 200-column terminal leaves a line of description marooned
half a metre from the flag it belongs to. This lays out at `WIDTH` and narrows
only when the terminal is smaller.

**No section that states a total.** The screen used to announce a detector
count, which is a claim, and a claim on a front door is the first thing a
reader checks and the first thing to go stale. Counts belong in the README
beside the list they count.

There is no `COMMANDS` section because there are no subcommands - one file
argument and four flags. Printing an empty heading to look like `gh` would be
furniture.
"""

from __future__ import annotations

import sys
import textwrap
from typing import TextIO

from . import __version__
from .report import Style
from .theme import FAINT, FOREGROUND, MUTED

REPOSITORY = "github.com/osint-shifu/unmasker"
SUMMARY = "Report what a human sees in a document against what a machine reads out of it."

#: The bar, and what to draw it with where a terminal cannot encode a block.
#: Same rule as `theme.GLYPHS`: the layout never changes, only the characters.
BLOCK = ("█", "#")

#: How much of the word the bar covers. Five of eight - short enough that `ker`
#: escapes, which is the point, and long enough to read as a redaction rather
#: than a typo.
COVERED = 5

#: What the screen lays out at, regardless of how wide the terminal is. Wide
#: enough for the longest description below, narrow enough that a flag and its
#: description stay in the same glance.
WIDTH = 78

INDENT = "  "

USAGE = (
    "unmasker <file> [options]",
    "unmasker <folder> [options]",
)

OPTIONS = (
    ("--json", "one object on stdout, for a pipeline to sort or filter"),
    ("--ocr", "render each page and read it back (needs ghostscript, tesseract)"),
    ("--width N", "wrap at N columns instead of measuring the terminal"),
    ("--version", "print the version and exit"),
    ("-h, --help", "the full option list"),
)

EXAMPLES = (
    ("unmasker leaked.pdf", "one document, reported for a person"),
    ("unmasker ~/cases/kowalski", "a folder, surveyed: which to open next"),
    ("unmasker bids.xlsx --json", "the same, for a pipeline"),
    ("unmasker scan.pdf --ocr", "when the technique is unknown"),
)

EXIT = (
    ("0", "read, searched, nothing found"),
    ("1", "read, searched, findings exist"),
    ("2", "could not be read"),
)

#: One line, because the first surprise a reader can have is pointing this at a
#: deck and being refused.
FORMATS = "PDF · DOCX · ODT · XLSX · ODS · text.  Presentations are refused."


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


#: Below this many columns for the description, the two-column layout stops
#: being one. A flag with four words wrapped against it is harder to read than
#: the same flag with its description on the next line.
NARROWEST = 24


def _rows(style: Style, width: int, rows: tuple[tuple[str, str], ...]) -> list[str]:
    """A left column sized to its own section - per section, never once per
    screen - with descriptions wrapping under themselves rather than under the
    name.

    Where the terminal is too narrow to hold both columns, the description goes
    on its own line underneath. Squeezing it into four columns instead is how a
    help screen ends up wider than the terminal it is printed in.
    """
    left = max(len(name) for name, _ in rows)
    room = width - len(INDENT) - left - 2
    stacked = room < NARROWEST

    out: list[str] = []
    for name, description in rows:
        if stacked:
            out.append(INDENT + style.ink(name, FOREGROUND))
            for line in textwrap.wrap(description, width=max(8, width - len(INDENT) * 2)) or [""]:
                out.append(INDENT * 2 + style.ink(line, MUTED))
            continue
        lines = textwrap.wrap(description, width=room) or [""]
        out.append(
            INDENT + style.ink(name.ljust(left), FOREGROUND) + "  " + style.ink(lines[0], MUTED)
        )
        for extra in lines[1:]:
            out.append(INDENT + " " * (left + 2) + style.ink(extra, MUTED))
    return out


def render(style: Style | None = None, stream: TextIO | None = None) -> str:
    style = style or Style()
    width = min(WIDTH, style.width)
    covered, underneath = mark(stream)

    def heading(text: str) -> list[str]:
        return ["", style.ink(text, FOREGROUND, bold=True)]

    out = [
        "",
        style.ink(covered, FOREGROUND, bold=True),
        style.ink(f"{underneath} {__version__}", FOREGROUND, bold=True),
    ]
    for line in textwrap.wrap(SUMMARY, width=width) or [""]:
        out.append(style.ink(line, MUTED))

    out += heading("USAGE")
    out += [INDENT + style.ink(line, FOREGROUND) for line in USAGE]

    out += heading("OPTIONS")
    out += _rows(style, width, OPTIONS)

    out += heading("EXAMPLES")
    out += _rows(style, width, EXAMPLES)

    out += heading("EXIT STATUS")
    out += _rows(style, width, EXIT)

    out += heading("FORMATS")
    for line in textwrap.wrap(FORMATS, width=width - len(INDENT)) or [""]:
        out.append(INDENT + style.ink(line, MUTED))

    out += ["", style.ink(REPOSITORY, FAINT), ""]
    return "\n".join(out)
