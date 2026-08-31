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

    drawn: tuple = ()
    """What the page paints, for readers that can see it - one
    `InterpretedPage` per page, empty for readers that only yield text.

    It lives here because the reader is the layer that opens the file, and a
    detector that has to ask what is under a black rectangle needs the text and
    the rectangle to have come out of the same reading of the same bytes.
    """

    revisions: object | None = None
    """A `RevisionRecord` for readers that can see tracked changes, else None.

    Typed loosely so the model does not have to know about OOXML. `None` and
    an empty record mean different things: the first is "this kind of file
    cannot carry tracked changes", the second is "it can and does not".
    """

    source: object | None = None
    """The file this came from. Kept because reading a page back means
    rendering it again, and a renderer needs the file rather than the reading
    of it."""

    metadata: object | None = None
    """A `Metadata` record for readers that can see one, else None.

    Typed loosely so the model does not have to know about PDF or OOXML.
    """

    sheets: object | None = None
    """A `SheetRecord` for readers that can see a workbook, else None.

    Separate from `units` on purpose, and it is the whole point of the
    spreadsheet reader: the cells an application agreed not to draw must not
    reach `units`, where they would be searched as though a person could see
    them - and then reported clean.
    """

    @property
    def has_text(self) -> bool:
        return any(u.text.strip() for u in self.units)
