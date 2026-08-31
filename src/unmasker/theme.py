"""Colour, and the one rule that governs it.

**Colour encodes how the tool knows, never what it found.** A reader learns the
classes once and can then triage by eye. There is no red-means-danger scheme
here and there must never be one: severity is the reader's judgement, and a tool
that colours by severity has made that judgement for them.

The palette is `filetrail`'s, deliberately. Its `DESIGN.md` is the design
language for both tools, and someone who has learned the hues there should not
have to learn them again. `direct` takes the green slot that `filetrail` gives
to `recorded`: in both, it is the strongest class and it means *this was
observed, not inferred*.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import TextIO

from .findings import Basis


class Depth(IntEnum):
    NONE = 0
    ANSI16 = 1
    ANSI256 = 2
    TRUECOLOR = 3


@dataclass(frozen=True)
class Ink:
    hex: str
    ansi256: int
    ansi16: int


# Evidence classes. The colour of a finding is keyed to its Basis and nothing
# else.
INK: dict[Basis, Ink] = {
    Basis.DIRECT: Ink("#5faf87", 71, 32),
    Basis.CIRCUMSTANTIAL: Ink("#d7af5f", 179, 33),
    Basis.SELF_REPORTED: Ink("#5f87af", 68, 34),
}

FOREGROUND = Ink("#d0d0d0", 252, 37)
MUTED = Ink("#8a8a8a", 245, 90)
FAINT = Ink("#585858", 240, 90)


def resolve_depth(stream: TextIO | None = None, env: dict | None = None) -> Depth:
    """Resolve once, at startup, from the stream and the environment.

    A terminal that cannot colour gets the same layout in plain text, never a
    different one.
    """
    stream = stream if stream is not None else sys.stdout
    env = env if env is not None else os.environ

    if env.get("NO_COLOR") is not None:
        return Depth.NONE
    if not getattr(stream, "isatty", lambda: False)():
        return Depth.NONE

    term = env.get("TERM", "")
    if term == "dumb":
        return Depth.NONE
    if env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return Depth.TRUECOLOR
    if "256" in term:
        return Depth.ANSI256
    return Depth.ANSI16


def paint(text: str, ink: Ink, depth: Depth, *, bold: bool = False) -> str:
    """Wrap `text` in the escape for `ink` at `depth`, or return it unchanged."""
    if depth is Depth.NONE or not text:
        return f"\x1b[1m{text}\x1b[0m" if bold and depth is not Depth.NONE else text

    if depth is Depth.TRUECOLOR:
        r, g, b = (int(ink.hex[i : i + 2], 16) for i in (1, 3, 5))
        code = f"38;2;{r};{g};{b}"
    elif depth is Depth.ANSI256:
        code = f"38;5;{ink.ansi256}"
    else:
        code = str(ink.ansi16)

    return f"\x1b[{'1;' if bold else ''}{code}m{text}\x1b[0m"


# Box drawing, with an ASCII fallback for terminals that cannot encode it. The
# fallback is a different glyph, never a different layout.
GLYPHS = {
    "bullet": ("●", "*"),
    "pipe": ("│", "|"),
    "rule": ("─", "-"),
}


def glyphs(stream: TextIO | None = None) -> dict[str, str]:
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "ascii"
    out = {}
    for name, (rich, plain) in GLYPHS.items():
        try:
            rich.encode(encoding)
            out[name] = rich
        except (UnicodeEncodeError, LookupError):
            out[name] = plain
    return out
