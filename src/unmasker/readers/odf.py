"""OpenDocument body text.

`unmasker` refused .odt files outright until this existed, which was a large
refusal: ODF is LibreOffice's native format and the one a great deal of
European government and legal work is written in.

Like the DOCX reader, this reads what a reader *sees* - and in ODF that takes
more care than it does in OOXML, because the two things it must not read live
**inside the body** rather than in separate parts of the zip.
`<text:tracked-changes>` sits at the top of `office:text` and holds every
deleted passage; `<office:annotation>` sits inline in the paragraph it belongs
to and holds a comment. Extracting the body naively reports both as ordinary
visible prose, which is exactly backwards: a reader of the page sees neither.

They are read separately, by `unmasker.odf.revisions`, which keeps the author
and the date attached to them.

No new dependency: an .odt is a zip of XML and both are in the standard library.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from ..metadata import read_odf as read_odf_metadata
from ..metadata.detectors import describe
from ..odf.revisions import read_revisions
from .model import Extraction, TextUnit, UnreadableFile

TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"

# Never part of the visible page, and both of them inline in the body.
NOT_ON_THE_PAGE = (f"{TEXT}tracked-changes", f"{OFFICE}annotation")

PARAGRAPHS = (f"{TEXT}p", f"{TEXT}h")


def _paragraph_text(node) -> str:
    out: list[str] = []

    def walk(element) -> None:
        for child in element:
            if child.tag in NOT_ON_THE_PAGE:
                # Skip the subtree but keep what follows it on the line.
                if child.tail:
                    out.append(child.tail)
                continue
            if child.tag == f"{TEXT}s":
                out.append(" " * int(child.get(f"{TEXT}c", "1") or 1))
            elif child.tag == f"{TEXT}tab":
                out.append("\t")
            elif child.tag == f"{TEXT}line-break":
                out.append("\n")
            if child.text:
                out.append(child.text)
            walk(child)
            if child.tail:
                out.append(child.tail)

    if node.text:
        out.append(node.text)
    walk(node)
    return "".join(out)


def _body_text(root) -> str:
    """One line per paragraph, skipping paragraphs inside what is not on the page."""
    skipped: set[int] = set()
    for hidden in NOT_ON_THE_PAGE:
        for node in root.iter(hidden):
            for inner in node.iter():
                skipped.add(id(inner))

    lines = []
    for node in root.iter():
        if node.tag not in PARAGRAPHS or id(node) in skipped:
            continue
        lines.append(_paragraph_text(node))
    return "\n".join(lines)


def read_odf(path: Path) -> Extraction:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc

    with archive:
        names = archive.namelist()
        if "content.xml" not in names:
            raise UnreadableFile(f"{path.name} is a zip but not an OpenDocument file")

        units: list[TextUnit] = []
        remarks: list[str] = []
        for part in ("content.xml", "styles.xml"):
            if part not in names:
                continue
            try:
                root = ElementTree.fromstring(archive.read(part))
            except ElementTree.ParseError as exc:
                remarks.append(f"{part} is not well-formed XML and was skipped: {exc}")
                continue
            text = _body_text(root)
            if text.strip():
                units.append(TextUnit(text=text))

        record = read_revisions(archive)
        remarks.extend(record.remarks)

        metadata = read_odf_metadata(archive)
        remarks.extend(metadata.remarks)
        remarks.extend(describe(metadata))

        if not units:
            remarks.append("the document body holds no text, so there was nothing to search")

    return Extraction(
        kind="odf",
        units=tuple(units),
        remarks=tuple(remarks),
        revisions=record,
        metadata=metadata,
    )
