"""Word 97, Excel 97 and PowerPoint 97: the compound-file formats.

These are not zips and not XML. Each is a filesystem in a file, read by
`unmasker.ole2`, and what this reader takes out of it is the metadata: the two
property streams every Office application has written since 1997, holding the
author, the title, the company, the revision count and the timestamps.

**The document's text is not read.** The binary formats inside - the
`WordDocument` stream and its piece table, the `Workbook` stream's BIFF
records - are each a separate problem of their own size, and none is solved
here. That is stated in a remark and carried on the extraction as
`text_unread`, because a document whose text was never read is not a document
whose text came back clean, and the metadata detector is told not to claim a
gap it could not look for.
"""

from __future__ import annotations

from pathlib import Path

from ..metadata import Field, Metadata
from ..metadata.detectors import describe
from ..ole2 import CompoundFile, NotACompoundFile
from ..ole2.properties import read_properties
from .model import Extraction, UnreadableFile

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

    remarks.append(
        f"this is {described}, and its text is stored in a binary format this "
        "tool does not read yet - so nothing here was searched for hidden "
        "characters, and what its metadata says was not compared against what "
        "the document shows"
    )

    # Read and reported, even though none of it can be a finding here: with no
    # text to compare against there is no gap to claim, and a value this tool
    # read and mentioned to nobody would be the worst of both.
    metadata = Metadata(fields=tuple(fields), container="ole2")
    remarks.extend(describe(metadata))

    # The content fields, stated plainly. They cannot be called undisclosed -
    # nothing compared them against a page - but a value this tool read and
    # mentioned to nobody is worse than either answer. Whether the document
    # shows them is left to the person holding it, which is the honest place
    # for a judgement this tool did not make.
    said = [f"{entry.name} {entry.value}" for entry in metadata.by_role("content")]
    if said:
        remarks.append(
            "the file says of itself: "
            + "; ".join(said)
            + " - not compared against the document's own text, which was not read"
        )

    return Extraction(
        kind=kind,
        units=(),
        remarks=tuple(remarks),
        source=path,
        metadata=metadata,
        text_unread=True,
    )


__all__ = ["read_legacy"]
