"""The evidence model.

Two rules from `CONTRIBUTING.md` shape everything here, and both were paid for in the
sibling project.

**Different questions are not ranked against each other.** A `Finding` carries
no score, and nothing sorts findings by strength. A page can have a rectangle
over its text *and* invisible characters *and* stale metadata; those are three
findings, not one winner. `filetrail` printed the winner, and a geotagged
photograph that had been downloaded reported its URL and no GPS at all.

**Nothing implies a precision we do not have.** `Basis` is a word, not a number,
because `55` reads as a probability and never was one. A word can be argued
with by the person reading the report, which is the whole point: this tool shows
evidence and lets its reader draw the conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Basis(Enum):
    """How we know. Never how bad it is.

    Colour in the report is keyed to this and to nothing else, so a reader
    learns the classes once and can then triage by eye.
    """

    DIRECT = "direct"
    """The bytes are in the file and we read them out. Nothing is inferred.

    A zero-width character either is at that offset or is not.
    """

    CIRCUMSTANTIAL = "circumstantial"
    """Consistent with hiding, and with innocent explanations too.

    A word spanning two scripts may be a homoglyph attack or may be how someone
    writes. The tool reports the observation, not a motive.
    """

    SELF_REPORTED = "self-reported"
    """The file's own account of itself, believed only as far as a file can be.

    Producer strings, timestamps, tracked-change authorship.
    """


@dataclass(frozen=True, order=True)
class Location:
    """Where in the document. Whichever coordinates the reader can act on.

    A text file has lines and columns; a PDF page has a page number and, once
    the interpreter lands, a position on it. Both are optional because a finding
    about the file as a whole has neither.
    """

    line: int | None = None
    column: int | None = None
    page: int | None = None

    inside: str = ""
    """The carried file this finding came out of, where it is not the document
    itself. A hidden sheet in a workbook and a hidden sheet in a workbook that
    a report carries are not the same statement, and a reader has to be able
    to tell which one is in front of them."""

    def __str__(self) -> str:
        parts = []
        if self.page is not None:
            parts.append(f"page {self.page}")
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.column is not None:
            parts.append(f"column {self.column}")
        where = ", ".join(parts) if parts else "whole file"
        return f"in {self.inside}" if self.inside else where

    @property
    def sort_key(self) -> tuple[int, int, int]:
        """Document order. Missing coordinates sort first, not last."""
        return (self.page or 0, self.line or 0, self.column or 0)


@dataclass(frozen=True)
class Finding:
    """One place where what a human sees and what a machine reads disagree.

    `human_sees` and `machine_reads` are the report. Everything else positions
    them or says how we know. A finding that cannot fill both of those columns
    is not a finding this tool knows how to state.
    """

    detector: str
    """Stable slug: `zero-width`, `bidi-control`, `tag-characters`,
    `mixed-script`. Groups the report and keys `--json`."""

    basis: Basis
    summary: str
    """One line naming the gap, in words a reader can disagree with."""

    human_sees: str
    """The line as it renders. Hidden characters gone, overrides applied."""

    machine_reads: str
    """The same line as a parser gets it, with what the eye misses made
    explicit."""

    location: Location = field(default_factory=Location)

    codepoints: tuple[str, ...] = ()
    """Every codepoint behind this finding, in order, as `U+XXXX`. Not a
    sample - `CONTRIBUTING.md` forbids truncation, and a reader who has to run the
    tool again to see the rest was told less than the tool knew."""

    decoded: str | None = None
    """What the hidden characters spell, when they spell anything. Tag
    characters carry readable text; zero-width runs generally do not."""

    def as_dict(self) -> dict:
        """The `--json` shape. Ordering here is the ordering a consumer sees."""
        out: dict = {
            "detector": self.detector,
            "basis": self.basis.value,
            "summary": self.summary,
            "human_sees": self.human_sees,
            "machine_reads": self.machine_reads,
            "location": {
                k: v
                for k, v in (
                    ("page", self.location.page),
                    ("line", self.location.line),
                    ("column", self.location.column),
                    # Omitted when empty, like the rest: adding a key a
                    # consumer may ignore does not change the shape, so
                    # SCHEMA stays where it is.
                    ("inside", self.location.inside or None),
                )
                if v is not None
            },
            "codepoints": list(self.codepoints),
        }
        if self.decoded is not None:
            out["decoded"] = self.decoded
        return out
