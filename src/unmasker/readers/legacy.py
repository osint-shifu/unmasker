"""Word 97, Excel 97 and PowerPoint 97: the compound-file formats.

These are not zips and not XML. Each is a filesystem in a file, read by
`unmasker.ole2`, and what this reader takes out of it is the metadata: the two
property streams every Office application has written since 1997, holding the
author, the title, the company, the revision count and the timestamps.

**Word's text is read; the other two are not.** `unmasker.word` reads the
`WordDocument` stream - the piece table, the stories a document keeps its
footnotes and headers and comments in, and the property tables that say which
characters are deleted or hidden. The `Workbook` stream's BIFF records and the
PowerPoint record stream are each a separate problem of their own size and
neither is solved.

Where the text was not read, that is stated in a remark **naming the format**
and carried on the extraction as `text_unread`. Loosening that remark to keep
covering Word once Word became readable is exactly how a report ends up
claiming a search that never happened, so the corpus holds a .xls to fail the
test if it ever slips: a document whose text was never read is not a document
whose text came back clean, and the metadata detector is told not to claim a
gap it could not look for.
"""

from __future__ import annotations

from pathlib import Path

from ..metadata import Field, Metadata
from ..metadata.detectors import describe
from ..ole2 import CompoundFile, NotACompoundFile
from ..ole2.properties import read_properties
from ..revisions import RevisionRecord
from ..word import NotAWordDocument, read_word
from .model import Extraction, TextUnit, UnreadableFile

SUMMARY = "\x05SummaryInformation"
DOCUMENT_SUMMARY = "\x05DocumentSummaryInformation"

#: Which application wrote it, by the stream only that application writes.
FLAVOURS = (
    ("WordDocument", "doc", "a Word 97 document"),
    ("Workbook", "xls", "an Excel 97 workbook"),
    ("Book", "xls", "an Excel 5 workbook"),
    ("PowerPoint Document", "ppt", "a PowerPoint 97 presentation"),
)

#: What each property means, so a value is read as what it is rather than
#: matched by shape. `CONTRIBUTING.md`: the name of a field is evidence.
#: What a field instruction has to hold to be quoted rather than counted.
#: The same rule `metadata-path` follows: a value that names a location is
#: worth reading, and the kind is the test - not how interesting it looks.
LOCATIONS = ("://", "\\\\", "file:", "C:\\", "/")


ROLES = {
    "title": "content",
    "subject": "content",
    "author": "content",
    "keywords": "content",
    "comments": "content",
    "last saved by": "content",
    "manager": "content",
    "company": "content",
    "category": "content",
    "application name": "tool",
    "template": "path",
    "create time": "time",
    "last saved time": "time",
    "last printed": "time",
}


def _covered(document) -> str:
    """Which of a document's stories were read, named the way a person would.

    A .doc lays every part of its text - the paragraphs, the footnotes, the
    headers, the text boxes - end to end in one space, and more than half of a
    real document is routinely outside the part a reader would call "the
    document". Saying which were read is the difference between a search and a
    claim about one.
    """
    named = [story.name for story in document.stories]
    if not named:
        return "this document holds no text on any of its pages to search"
    return "searched " + ", ".join(named)


def _fields(document) -> list[str]:
    """What the file computes rather than stores, where that names a place.

    Every table of contents and page number in every document is a field, so
    counting them all as findings would fire on nearly every real file. The
    ones that name a location get quoted in full, which is the rule
    `metadata-path` already follows.
    """
    if not document.fields:
        return []
    named = [
        code.instruction
        for code in document.fields
        if any(mark in code.instruction for mark in LOCATIONS)
    ]
    rest = len(document.fields) - len(named)
    out = []
    if named:
        out.append(
            "the page shows the result of "
            + ("a field" if len(named) == 1 else f"{len(named)} fields")
            + " whose instruction names a location, and the instruction is not "
            "shown anywhere: " + "; ".join(named)
        )
    if rest:
        out.append(
            f"{rest} further field"
            + ("" if rest == 1 else "s")
            + " compute what the page shows - a page number, a reference, a "
            "table of contents - and none of them names a location"
        )
    return out


def read_legacy(path: Path) -> Extraction:
    """A compound-file Office document, read for what it says about itself."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise UnreadableFile(f"cannot read {path}: {exc}") from exc

    try:
        compound = CompoundFile(data)
    except NotACompoundFile as exc:
        raise UnreadableFile(f"{path.name} is not a readable compound file: {exc}") from exc

    kind, described = "ole2", "a compound file this reader does not recognise"
    for stream, flavour, wording in FLAVOURS:
        if stream in compound.names:
            kind, described = flavour, wording
            break

    fields: list[Field] = []
    remarks: list[str] = []
    for stream in (SUMMARY, DOCUMENT_SUMMARY):
        if stream not in compound.names:
            continue
        try:
            found = read_properties(compound.read(stream))
        except Exception as exc:  # noqa: BLE001 - a damaged table is not fatal
            remarks.append(f"{stream.lstrip(chr(5))} could not be read: {exc}")
            continue
        for name, value in found.items():
            fields.append(
                Field(
                    name=name,
                    value=value,
                    part=stream.lstrip(chr(5)),
                    role=ROLES.get(name.lower(), "other"),
                )
            )

    if not fields:
        remarks.append(
            "this file states nothing about itself in either property stream"
        )

    units: tuple[TextUnit, ...] = ()
    record: RevisionRecord | None = None
    document = None
    unread = True

    if kind == "doc":
        try:
            document = read_word(compound)
        except NotAWordDocument as exc:
            remarks.append(
                f"this is {described} whose text could not be read ({exc}), so "
                "nothing in it was searched for hidden characters"
            )
        else:
            remarks.extend(document.remarks)
            unread = document.encrypted or document.properties_unread
            if not unread:
                units = tuple(TextUnit(text=story.text) for story in document.stories)
                remarks.append(_covered(document))
                remarks.extend(_fields(document))
            record = RevisionRecord(
                revisions=document.revisions, comments=document.comments
            )
    else:
        remarks.append(
            f"this is {described}, and its text is stored in a binary format this "
            "tool does not read - so nothing here was searched for hidden "
            "characters, and what its metadata says was not compared against what "
            "the document shows"
        )

    carried = sorted({name.split("/")[0] for name in compound.names if "/" in name})
    if carried:
        remarks.append(
            "this file carries whole objects inside it, in "
            + "; ".join(carried)
            + " - they were not opened, so nothing in them was searched"
        )

    # Read and reported whether or not it can be a finding: a value this tool
    # read and mentioned to nobody would be the worst of both.
    metadata = Metadata(fields=tuple(fields), container="ole2")
    remarks.extend(describe(metadata))

    if unread:
        # The content fields, stated plainly. They cannot be called
        # undisclosed - nothing compared them against a page - but a value
        # this tool read and mentioned to nobody is worse than either answer.
        # Whether the document shows them is left to the person holding it,
        # which is the honest place for a judgement this tool did not make.
        said = [f"{entry.name} {entry.value}" for entry in metadata.by_role("content")]
        if said:
            remarks.append(
                "the file says of itself: "
                + "; ".join(said)
                + " - not compared against the document's own text, which was not read"
            )

    return Extraction(
        kind=kind,
        units=units,
        remarks=tuple(remarks),
        source=path,
        metadata=metadata,
        revisions=record,
        word=document,
        text_unread=unread,
    )


__all__ = ["read_legacy"]
