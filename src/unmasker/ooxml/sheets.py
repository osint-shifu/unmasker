"""A workbook's sheets, and which of them an application agreed not to draw.

SpreadsheetML states hiding on the thing being hidden, which makes it the
easier of the two families to read - and hides a trap in the easiness.

    <sheet name="Workings" state="hidden"/>       a whole sheet
    <row r="4" hidden="true">                     a row
    <col min="4" max="4" hidden="true"/>          a *range* of columns

Two producer facts, both measured against a file LibreOffice Calc wrote rather
than read out of the specification:

- **`hidden` is written on every row, saying `false` on most of them.** A
  reader that tests whether the attribute is present rather than what it says
  reports every row in the workbook as concealed.
- **`min` and `max` are a range, not an identifier.** One `col` element can
  hide forty columns, and each of them has to be counted or the values in
  thirty-nine of them go unreported.

Cell text arrives three ways and all three are needed: `t="s"` is an index into
`xl/sharedStrings.xml`, `t="inlineStr"` carries the characters in the cell, and
a cell with no `t` at all holds a number written out in `<v>`.

Comments live in their own part, reached through the worksheet's relationships,
with authors held in a separate list and referenced by position. They are the
same finding a Word comment and a PDF annotation produce, so they come back as
the `Comment` the shared revision record already defines.

Change tracking lives in `xl/revisions/`, which only a shared workbook has, and
it is the part of this format most easily read wrongly. Three things about it:

- **It is one log part per editing session**, each reached by relationship from
  `revisionHeaders.xml`. Reading `revisionLog1.xml` and stopping reports one
  change out of however many there are, and gives no sign of having stopped.
- **The author and the date are on the header**, not on the change, so an
  `rcc` read on its own has nobody attached to it.
- **`<nc>` holds the old value.** LibreOffice writes the "new cell" element
  with the *previous* contents, so a reader that believed the log would report
  a cell that changed from 240000 to 240000. The current value comes out of the
  sheet, which is where a person would look.

No new dependency: an .xlsx is a zip of XML and both are in the standard
library.
"""

from __future__ import annotations

import posixpath
import zipfile
from xml.etree import ElementTree

from ..revisions import Comment
from ..sheets import Cell, CellChange, Sheet, SheetRecord, TrackedDeletion

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

WORKBOOK = "xl/workbook.xml"

# `state` values other than these two mean the sheet is shown.
HIDDEN_STATES = {"hidden": "hidden", "veryHidden": "very hidden"}


def _is_true(value: str | None) -> bool:
    """SpreadsheetML writes booleans four ways, and says `false` out loud."""
    return (value or "").strip().lower() in ("1", "true", "on")


def _column_of(reference: str) -> int:
    """`B7` -> 2. The letters are the column; the digits are the row."""
    index = 0
    for character in reference:
        if not character.isalpha():
            break
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index


def _relationships(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    """`rId3` -> the part it points at, resolved against the part's own folder."""
    folder = posixpath.dirname(part)
    rels = posixpath.join(folder, "_rels", posixpath.basename(part) + ".rels")
    if rels not in archive.namelist():
        return {}
    try:
        root = ElementTree.fromstring(archive.read(rels))
    except ElementTree.ParseError:
        return {}

    out = {}
    for node in root.iter(f"{PKG_REL}Relationship"):
        target = node.get("Target") or ""
        identifier = node.get("Id")
        if not identifier or not target or target.startswith(("http://", "https://")):
            continue
        out[identifier] = posixpath.normpath(posixpath.join(folder, target)).lstrip("/")
    return out


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    part = "xl/sharedStrings.xml"
    if part not in archive.namelist():
        return []
    try:
        root = ElementTree.fromstring(archive.read(part))
    except ElementTree.ParseError:
        return []
    # A string is split across `t` elements wherever part of it is formatted
    # differently, so every one of them is joined rather than the first taken.
    return ["".join(t.text or "" for t in item.iter(f"{MAIN}t")) for item in root.iter(f"{MAIN}si")]


def _cell_text(cell, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "s":
        value = cell.find(f"{MAIN}v")
        try:
            return shared[int((value.text or "").strip())] if value is not None else ""
        except (ValueError, IndexError):
            return ""
    if kind == "inlineStr":
        node = cell.find(f"{MAIN}is")
        return "".join(t.text or "" for t in node.iter(f"{MAIN}t")) if node is not None else ""
    value = cell.find(f"{MAIN}v")
    return (value.text or "") if value is not None else ""


def _read_worksheet(xml: bytes, name: str, hidden: str | None, shared: list[str]) -> Sheet:
    root = ElementTree.fromstring(xml)

    hidden_columns: set[int] = set()
    for column in root.iter(f"{MAIN}col"):
        if not _is_true(column.get("hidden")):
            continue
        try:
            first, last = int(column.get("min", "0")), int(column.get("max", "0"))
        except ValueError:
            continue
        # A single `col` can hide a range. Excel writes one element for a whole
        # selection, so the range has to be walked out.
        hidden_columns.update(range(first, last + 1))

    cells: list[Cell] = []
    hidden_rows: set[int] = set()
    for index, row in enumerate(root.iter(f"{MAIN}row"), start=1):
        try:
            number = int(row.get("r") or index)
        except ValueError:
            number = index
        if _is_true(row.get("hidden")):
            hidden_rows.add(number)
        for position, cell in enumerate(row.iter(f"{MAIN}c"), start=1):
            column = _column_of(cell.get("r") or "") or position
            text = _cell_text(cell, shared)
            if text:
                cells.append(Cell(row=number, column=column, text=text))

    return Sheet(
        name=name,
        hidden=hidden,
        cells=tuple(cells),
        hidden_rows=frozenset(hidden_rows),
        hidden_columns=frozenset(hidden_columns),
    )


def _read_comments(archive: zipfile.ZipFile, part: str) -> list[Comment]:
    """One sheet's cell comments, with the author each is attributed to."""
    found: list[Comment] = []
    for target in _relationships(archive, part).values():
        if not posixpath.basename(target).startswith("comments"):
            continue
        if target not in archive.namelist():
            continue
        try:
            root = ElementTree.fromstring(archive.read(target))
        except ElementTree.ParseError:
            continue
        authors = [a.text or "" for a in root.iter(f"{MAIN}author")]
        for comment in root.iter(f"{MAIN}comment"):
            text = "".join(t.text or "" for t in comment.iter(f"{MAIN}t"))
            try:
                author = authors[int(comment.get("authorId", "0"))]
            except (ValueError, IndexError):
                author = ""
            found.append(
                Comment(
                    text=text,
                    # SpreadsheetML records no date on a cell comment. Saying
                    # so is the honest answer; inventing one from the file's
                    # modification time would be inventing evidence.
                    author=author or None,
                    date=None,
                )
            )
    return found


def _row_of(reference: str) -> int:
    digits = "".join(c for c in reference if c.isdigit())
    return int(digits) if digits else 0


def _read_revision_log(
    archive: zipfile.ZipFile, sheet_of: dict[str, str]
) -> tuple[list[CellChange], list[TrackedDeletion], list[str]]:
    """Cell changes out of `xl/revisions/`, which only a shared workbook has.

    The log holds one `rcc` per changed cell, with `oc` for the old cell and
    `nc` for the new one. **`nc` is not trusted**: LibreOffice's export writes
    the *old* value into it, so a reader that believed the log would report a
    cell that changed from 240000 to 240000. The current value is read out of
    the sheet instead, which is where a person would look.

    Who and when live in `revisionHeaders.xml` rather than on the change, one
    header per editing session, so they are matched by the relationship the
    header points at.
    """
    names = set(archive.namelist())
    headers = "xl/revisions/revisionHeaders.xml"
    if headers not in names:
        return [], [], []

    try:
        root = ElementTree.fromstring(archive.read(headers))
    except ElementTree.ParseError as exc:
        return [], [], [f"{headers} is not well-formed XML and was skipped: {exc}"]

    targets = _relationships(archive, headers)
    changes: list[CellChange] = []
    deletions: list[TrackedDeletion] = []
    remarks: list[str] = []
    for header in root.iter(f"{MAIN}header"):
        part = targets.get(header.get(f"{DOC_REL}id") or "")
        if part is None or part not in names:
            continue
        author = header.get("userName") or None
        date = header.get("dateTime") or None
        try:
            log = ElementTree.fromstring(archive.read(part))
        except ElementTree.ParseError as exc:
            remarks.append(f"{part} is not well-formed XML and was skipped: {exc}")
            continue

        for change in log.iter(f"{MAIN}rcc"):
            old = change.find(f"{MAIN}oc")
            if old is None:
                continue
            reference = old.get("r") or ""
            value = old.find(f"{MAIN}v")
            text = (value.text or "") if value is not None else ""
            if not text:
                # A string previous value is `t="inlineStr"` with an `<is>`,
                # where a numeric one is `t="n"` with a `<v>`. Both forms
                # appear in one log, so both have to be read.
                node = old.find(f"{MAIN}is")
                if node is not None:
                    text = "".join(t.text or "" for t in node.iter(f"{MAIN}t"))
            changes.append(
                CellChange(
                    sheet=sheet_of.get(change.get("sId") or "", "(unnamed)"),
                    row=_row_of(reference),
                    column=_column_of(reference),
                    previous=text,
                    author=author,
                    date=date,
                )
            )

        for deletion in log.iter(f"{MAIN}rrc"):
            where = deletion.get("ref") or "an unstated range"
            sheet = sheet_of.get(deletion.get("sId") or "", "(unnamed)")
            deletions.append(
                TrackedDeletion(sheet=sheet, where=where, author=author, date=date)
            )
            remarks.append(
                f"a tracked {deletion.get('action') or 'deletion'} at {where} "
                f"by {author or 'an editor the file does not name'} carries no content "
                "in this file, so there is nothing to quote"
            )

    return changes, deletions, remarks


def read_sheets(archive: zipfile.ZipFile) -> tuple[SheetRecord, tuple[Comment, ...]]:
    names = set(archive.namelist())
    if WORKBOOK not in names:
        return SheetRecord(remarks=("the workbook has no xl/workbook.xml and was not read",)), ()

    try:
        book = ElementTree.fromstring(archive.read(WORKBOOK))
    except ElementTree.ParseError as exc:
        return SheetRecord(remarks=(f"xl/workbook.xml is not well-formed XML: {exc}",)), ()

    targets = _relationships(archive, WORKBOOK)
    shared = _shared_strings(archive)

    sheets: list[Sheet] = []
    comments: list[Comment] = []
    remarks: list[str] = []
    # `rcc sId="1"` names a sheet by its `sheetId`, which is not its position
    # and not its name. A reader that used the index would report the change
    # against whichever sheet happened to be there.
    sheet_of: dict[str, str] = {}
    for entry in book.iter(f"{MAIN}sheet"):
        name = entry.get("name") or "(unnamed)"
        sheet_of[entry.get("sheetId") or ""] = name
        hidden = HIDDEN_STATES.get((entry.get("state") or "").strip())
        part = targets.get(entry.get(f"{DOC_REL}id") or "")
        if part is None or part not in names:
            # The workbook names a sheet whose part is absent. "Searched and
            # found nothing" and "there was nothing to search" are different
            # answers, and a reader must not be handed the first for the
            # second.
            remarks.append(f'sheet "{name}" is listed in the workbook and its part is missing')
            sheets.append(Sheet(name=name, hidden=hidden))
            continue
        try:
            sheets.append(_read_worksheet(archive.read(part), name, hidden, shared))
        except ElementTree.ParseError as exc:
            remarks.append(f'sheet "{name}" is not well-formed XML and was skipped: {exc}')
            sheets.append(Sheet(name=name, hidden=hidden))
            continue
        comments.extend(_read_comments(archive, part))

    changes, deletions, log_remarks = _read_revision_log(archive, sheet_of)
    remarks.extend(log_remarks)

    return (
        SheetRecord(
            sheets=tuple(sheets),
            changes=tuple(changes),
            deletions=tuple(deletions),
            remarks=tuple(remarks),
        ),
        tuple(comments),
    )
