"""What a reader hands back, and why it carries more than a string.

**"Nothing found" has two meanings.** It can mean *searched, and it is not
there*; it can mean *there was nothing to search*. `filetrail` grew a `doctor`
command because that difference kept getting lost between the code that knew it
and the report that printed it.

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
class Attachment:
    """A file travelling inside another file.

    `text` is the decoded content where the bytes are text and None where they
    are not. A binary attachment is still a finding - it is there, and the page
    does not say so - but quoting it would be noise rather than evidence.
    """

    name: str
    size: int
    text: str | None = None
    part: str = ""
    """Where in the container it was found, named the way the format names it:
    `/Names/EmbeddedFiles` in a PDF, an archive member elsewhere."""

    description: str = ""
    """What the bytes are, for an attachment that is not text.

    "Nothing" is the wrong answer for a file that is plainly there, and it is
    the answer an empty column gives. A reader who cannot be shown the content
    can still be told what kind of thing is sitting in the document."""


SIGNATURES = (
    (b"PK\x03\x04", "a zip archive"),
    (b"%PDF-", "a PDF"),
    (b"\xff\xd8\xff", "a JPEG"),
    (b"\x89PNG\r\n", "a PNG"),
    (b"\xd0\xcf\x11\xe0", "a legacy OLE2 compound file"),
    (b"{\\rtf", "an RTF document"),
)


def describe_bytes(head: bytes) -> str:
    """What the first bytes say this is. Content, not extension.

    The same rule the reader dispatch follows: a name is what somebody called
    the file, and a forensic tool has no business trusting it.
    """
    for signature, name in SIGNATURES:
        if head.startswith(signature):
            return name
    return "bytes in no format this tool recognises"


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

    attachments: tuple = ()
    """Whole files carried inside this one, as `Attachment` records.

    Empty means either that none were found or that this kind of file cannot
    hold any. The two are not distinguished here because no container this
    tool reads makes an attachment mandatory, so an empty tuple is never the
    surprising answer."""

    sha256: str = ""
    """The digest of the bytes that were read.

    A path is not a file. A report is something somebody is sent, and its
    reader cannot otherwise tell whether the file in front of them is the one
    it describes. Empty where the bytes were never read as a whole.
    """

    source: object | None = None
    """The file this came from. Kept because reading a page back means
    rendering it again, and a renderer needs the file rather than the reading
    of it."""

    metadata: object | None = None
    """A `Metadata` record for readers that can see one, else None.

    Typed loosely so the model does not have to know about PDF or OOXML.
    """

    image: object | None = None
    """A `Jpeg` record for readers that can see a picture, else None.

    The one container with no text in it at all, which is why `units` is empty
    and `has_text` is false: a photograph was not searched, and the report has
    to be able to say so rather than call it clean.
    """

    slides: object | None = None
    """A `SlideRecord` for readers that can see a deck, else None.

    The same split as `sheets`, and for the same reason: a slide an application
    skips must not reach `units`, where it would be searched as though an
    audience had seen it - and then reported clean.
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
