"""What a reader hands back, and why it carries more than a string.

`CLAUDE.md`: **"nothing found" has two meanings.** It can mean *searched, and it
is not there*; it can mean *there was nothing to search*. `filetrail` grew a
`doctor` command because that difference kept getting lost between the code that
knew it and the report that printed it.

So the difference is carried in the data, not reconstructed later. `has_text`
answers whether there was anything to search at all, and `remarks` says why not
in the reader's own words - the reader is the only layer that knows a PDF page
had no fonts in its resources, and by the time the report runs, that is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class UnreadableFile(Exception):
    """The file could not be turned into text at all.

    Distinct from a file that yielded no text: this one could not be opened,
    decoded or parsed. Refusing is the honest answer - a tool that guesses at
    a binary and reports what it found in the noise is worse than one that
    says it cannot read the file.
    """


@dataclass(frozen=True)
class TextUnit:
    """One addressable run of text, and where in the document it came from.

    A PDF page is a unit and carries its page number. A plain file is a single
    unit and carries none, because `line 12` is the whole address a reader
    needs there.
    """

    text: str
    page: int | None = None


@dataclass(frozen=True)
class Extraction:
    kind: str
    """`pdf`, `docx`, `plain`. Names the reader, not the file extension."""

    units: tuple[TextUnit, ...] = ()

    remarks: tuple[str, ...] = field(default_factory=tuple)
    """What the reader noticed about its own coverage, in plain words.

    Printed whether or not there are findings, because the reader is the only
    layer that can tell "this page has no text layer" from "this page has text
    and none of it is hidden".
    """

    @property
    def has_text(self) -> bool:
        return any(u.text.strip() for u in self.units)
