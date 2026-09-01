"""Spreadsheets, in both families.

A spreadsheet needs its own reader for one reason, and it is not that the XML
is different. Until this existed, an .ods fell through to the reader for text
documents - both are a zip with a `content.xml` in it - and `unmasker` printed
**nothing hidden found** over a workbook with a hidden column, a hidden row and
a hidden sheet in it, having read every concealed value as ordinary visible
prose. That is worse than not reading the file: it is the tool stating
something the evidence does not support, which `CLAUDE.md` forbids outright.

So the rule this reader is built on: **a cell an application has agreed not to
draw is not body text.** The visible cells go into the extraction, where the
character detectors will search them; the concealed ones stay in the sheet
record, where they are reported as what they are. It is the same split the
DOCX reader makes between `w:t` and `w:delText`, one container along.

A cell comment is the same finding a Word comment and a PDF annotation produce,
so it comes back on the shared revision record and is reported by the detector
that already exists for it.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from ..metadata import read_odf as read_odf_metadata
from ..metadata import read_ooxml
from ..metadata.detectors import describe
from ..odf.sheets import read_sheets as read_odf_sheets
from ..ooxml.sheets import read_sheets as read_ooxml_sheets
from ..revisions import Revision, RevisionRecord
from ..sheets import SheetRecord
from .model import Extraction, TextUnit, UnreadableFile

OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"

FLAVOURS = {
    "spreadsheet": f"{OFFICE}spreadsheet",
    "presentation": f"{OFFICE}presentation",
    "text": f"{OFFICE}text",
}


def odf_flavour(archive: zipfile.ZipFile) -> str:
    """Whether an OpenDocument archive is a text document, a spreadsheet or a
    presentation.

    The `mimetype` member answers it in one read, and the package format
    requires it. Where it is absent or says something unrecognised the body
    itself is asked, which is authoritative but costs a parse of the whole of
    `content.xml` - `office:body` sits after the automatic styles, so no
    prefix of the file can be trusted to contain it.
    """
    try:
        declared = archive.read("mimetype").decode("ascii", "replace").strip()
    except (KeyError, OSError):
        declared = ""
    for flavour in FLAVOURS:
        if declared.endswith(flavour):
            return flavour

    if "content.xml" not in archive.namelist():
        return "text"
    try:
        root = ElementTree.fromstring(archive.read("content.xml"))
    except (ElementTree.ParseError, OSError):
        return "text"
    for flavour, tag in FLAVOURS.items():
        if next(root.iter(tag), None) is not None:
            return flavour
    return "text"


def _open(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc


def _assemble(record: SheetRecord, comments, metadata) -> Extraction:
    units: list[TextUnit] = []
    remarks: list[str] = list(record.remarks)

    for sheet in record.sheets:
        text = sheet.visible_text
        if text.strip():
            units.append(TextUnit(text=text))

    # Change tracking goes into the shared revision record as well as staying
    # on the sheet record, and the split is deliberate. The sheet record has
    # the cell address and the current value, which is what `changed-cell`
    # reports. The revision record answers the *other* question - who worked on
    # this file and when - which is one fact about the document rather than one
    # fact per change, and is already implemented once.
    #
    # `cell-change` is not one of the kinds `deleted_text` treats as hiding, so
    # no change is reported twice; a tracked deletion carries no content in
    # either family, so it quotes nothing and is counted rather than reported.
    revisions = RevisionRecord(
        revisions=tuple(
            Revision(
                kind="cell-change",
                text=change.previous,
                author=change.author,
                date=change.date,
                part=change.sheet,
            )
            for change in record.changes
        )
        + tuple(
            Revision(
                kind="deletion",
                text="",
                author=deletion.author,
                date=deletion.date,
                part=deletion.sheet,
            )
            for deletion in record.deletions
        ),
        comments=tuple(comments),
    )

    if metadata is not None:
        remarks.extend(metadata.remarks)
        remarks.extend(describe(metadata))

    if not record.sheets:
        remarks.append("the workbook holds no sheets, so there was nothing to search")
    elif not units:
        # "Searched and found nothing" is not the same answer as "every sheet
        # that holds anything is one nobody can see", and a reader handed the
        # first for the second has drawn a conclusion this tool never made.
        remarks.append(
            "no sheet in this workbook shows any text; everything it holds is "
            "on a sheet, row or column that is not drawn"
            if any(sheet.cells for sheet in record.sheets)
            else "every sheet in this workbook is empty, so there was nothing to search"
        )

    return Extraction(
        kind="spreadsheet",
        units=tuple(units),
        remarks=tuple(remarks),
        revisions=revisions,
        metadata=metadata,
        sheets=record,
    )


def read_xlsx(path: Path) -> Extraction:
    with _open(path) as archive:
        if "xl/workbook.xml" not in archive.namelist():
            raise UnreadableFile(f"{path.name} is a zip but not a SpreadsheetML workbook")
        record, comments = read_ooxml_sheets(archive)
        return _assemble(record, comments, read_ooxml(archive))


def read_ods(path: Path) -> Extraction:
    with _open(path) as archive:
        if "content.xml" not in archive.namelist():
            raise UnreadableFile(f"{path.name} is a zip but not an OpenDocument file")
        record, comments = read_odf_sheets(archive)
        return _assemble(record, comments, read_odf_metadata(archive))
