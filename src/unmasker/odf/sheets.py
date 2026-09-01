"""An OpenDocument spreadsheet's sheets, and which of them are not drawn.

ODF states the same three facts as SpreadsheetML and states them differently,
which is the reason both readers exist rather than one.

    <table:table-row table:visibility="collapse">      a row
    <table:table-column table:visibility="collapse"/>  a column
    <table:table table:style-name="ta3">               a sheet - and the style
      ...<style:table-properties table:display="false"/>   says whether it shows

The sheet is the awkward one. Its visibility is not on the sheet: it is on a
named style somewhere else in the file, so a reader that looks for an attribute
finds nothing and reports a workbook with a concealed sheet as clean. Two
formats, the same fact, one of them behind an indirection.

Three more things this format does that the other does not:

- **A cell has no address.** Where SpreadsheetML writes `r="D4"`, ODF says
  nothing and means *the next one*, so position has to be counted - through
  `table:number-columns-repeated`, which stands in for a run of identical
  cells, and through `table:covered-table-cell`, which is a cell a merge has
  swallowed and which still occupies its column.
- **The repeats run to the edge of the sheet.** LibreOffice closes a table with
  a single row repeated 1 048 570 times. Materialising that is a million-entry
  set for no information at all, so hidden rows and columns are recorded as
  ranges while walking and resolved at the end against the ones that actually
  hold a value. A hidden empty row conceals nothing and is not a finding
  either way.
- **A comment sits inside the cell it annotates.** Its text is *not* the cell's
  text, and a reader that walks the subtree naively reports the comment as the
  value in the cell - the same trap `readers/odf.py` documents for annotations
  in a paragraph, arriving one container down.

`table:visibility` has a third value. `filter` means a filter is holding the row
back rather than a person having hidden it, which is a weaker claim, and the
two are kept apart here so the report can keep them apart.

No new dependency: an .ods is a zip of XML and both are in the standard library.
"""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from ..revisions import Comment
from ..sheets import Cell, CellChange, Sheet, SheetRecord, TrackedDeletion

TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
STYLE = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
DC = "{http://purl.org/dc/elements/1.1/}"

CELLS = (f"{TABLE}table-cell", f"{TABLE}covered-table-cell")

# A run repeated this many times is the empty tail of the sheet rather than
# content. The cap costs nothing: a range with no values in it produces no
# finding, and resolving the ranges against the cells that exist is what
# bounds this anyway.
TAIL = 4096


def _count(node, attribute: str) -> int:
    try:
        return max(1, int(node.get(attribute, "1") or 1))
    except ValueError:
        return 1


def _hidden_sheet_styles(root) -> set[str]:
    """Style names whose tables are not drawn.

    The indirection this reader exists for: `table:display="false"` is on the
    style, and the sheet only names it.
    """
    names = set()
    for container in (f"{OFFICE}automatic-styles", f"{OFFICE}styles"):
        for holder in root.iter(container):
            for style in holder.iter(f"{STYLE}style"):
                if style.get(f"{STYLE}family") != "table":
                    continue
                for properties in style.iter(f"{STYLE}table-properties"):
                    if (properties.get(f"{TABLE}display") or "").strip() == "false":
                        name = style.get(f"{STYLE}name")
                        if name:
                            names.add(name)
    return names


def _cell_text(cell) -> str:
    """The value shown in the cell, and not the comment sitting inside it."""
    annotations = {id(inner) for a in cell.iter(f"{OFFICE}annotation") for inner in a.iter()}
    lines = []
    for paragraph in cell.iter(f"{TEXT}p"):
        if id(paragraph) in annotations:
            continue
        lines.append("".join(paragraph.itertext()))
    return " ".join(line for line in lines if line)


def _cell_comments(cell) -> list[Comment]:
    found = []
    for annotation in cell.iter(f"{OFFICE}annotation"):
        creator = annotation.find(f"{DC}creator")
        date = annotation.find(f"{DC}date")
        text = " ".join(
            "".join(p.itertext()) for p in annotation.iter(f"{TEXT}p")
        ).strip()
        found.append(
            Comment(
                text=text,
                author=(creator.text or None) if creator is not None else None,
                date=(date.text or None) if date is not None else None,
            )
        )
    return found


def _note(ranges: dict[str, list[tuple[int, int]]], node, index: int, span: int) -> None:
    """File this row or column under the visibility it declares, if any.

    One branch per value rather than a membership test followed by a second
    discrimination later: mutation testing showed that arrangement had a
    redundant guard in it, where breaking the guard changed no answer because
    the later step re-decided the same question.
    """
    if span > TAIL:
        # The empty tail of the sheet rather than content.
        return
    visibility = (node.get(f"{TABLE}visibility") or "").strip()
    if visibility == "collapse":
        ranges["collapse"].append((index, index + span - 1))
    elif visibility == "filter":
        ranges["filter"].append((index, index + span - 1))


def _read_table(table, hidden: str | None) -> tuple[Sheet, list[Comment]]:
    columns: dict[str, list[tuple[int, int]]] = {"collapse": [], "filter": []}
    column_index = 1
    for column in table.iter(f"{TABLE}table-column"):
        span = _count(column, f"{TABLE}number-columns-repeated")
        _note(columns, column, column_index, span)
        column_index += span

    cells: list[Cell] = []
    comments: list[Comment] = []
    rows: dict[str, list[tuple[int, int]]] = {"collapse": [], "filter": []}
    row_index = 1
    for row in table.iter(f"{TABLE}table-row"):
        span = _count(row, f"{TABLE}number-rows-repeated")
        _note(rows, row, row_index, span)

        position = 1
        for cell in row:
            if cell.tag not in CELLS:
                continue
            width = _count(cell, f"{TABLE}number-columns-repeated")
            text = _cell_text(cell)
            comments.extend(_cell_comments(cell))
            if text and width <= TAIL:
                # A repeated cell holds the same value in each column it
                # covers, so each of them is a place that value can be hidden.
                for offset in range(width):
                    cells.append(Cell(row=row_index, column=position + offset, text=text))
            position += width
        row_index += span

    with_values_row = {c.row for c in cells}
    with_values_column = {c.column for c in cells}

    def resolve(ranges, populated):
        """Ranges narrowed to the rows or columns that actually hold a value.

        This is what bounds the walk. LibreOffice closes a table with rows
        repeated to row 1 048 576, and a hidden empty row conceals nothing.
        """
        out: set[int] = set()
        for first, last in ranges:
            out.update(index for index in populated if first <= index <= last)
        return frozenset(out)

    sheet = Sheet(
        name=table.get(f"{TABLE}name") or "(unnamed)",
        hidden=hidden,
        cells=tuple(cells),
        hidden_rows=resolve(rows["collapse"], with_values_row),
        hidden_columns=resolve(columns["collapse"], with_values_column),
        filtered_rows=resolve(rows["filter"], with_values_row),
    )
    return sheet, comments


def _change_info(node) -> tuple[str | None, str | None]:
    info = node.find(f"{OFFICE}change-info")
    if info is None:
        return None, None
    creator = info.find(f"{DC}creator")
    date = info.find(f"{DC}date")
    return (
        (creator.text or None) if creator is not None else None,
        (date.text or None) if date is not None else None,
    )


def _previous_value(node) -> str:
    """The value a tracked change took out of the cell.

    LibreOffice writes it **two different ways depending on its type**, and a
    reader that knows one of them reads half the changes and then reports the
    file as though that were all of them:

        a number   <table:change-track-table-cell office:value="240000"/>
                   - the `<text:p>` the source had is stripped
        a string   <table:change-track-table-cell><text:p>rejected</text:p>
                   - and no `office:value` at all

    Measured against a file LibreOffice wrote, not read out of the
    specification, which describes both and says nothing about which appears.
    """
    for cell in node.iter(f"{TABLE}change-track-table-cell"):
        paragraphs = " ".join("".join(p.itertext()) for p in cell.iter(f"{TEXT}p")).strip()
        if paragraphs:
            return paragraphs
        value = cell.get(f"{OFFICE}value")
        if value is not None:
            return value
    return ""


def _read_tracked_changes(
    root, names: list[str]
) -> tuple[list[CellChange], list[TrackedDeletion], list[str]]:
    changes: list[CellChange] = []
    deletions: list[TrackedDeletion] = []
    remarks: list[str] = []
    for tracked in root.iter(f"{TABLE}tracked-changes"):
        for change in tracked.iter(f"{TABLE}cell-content-change"):
            address = change.find(f"{TABLE}cell-address")
            if address is None:
                continue
            try:
                # ODF counts both from zero. Passing that on would send a
                # reader to the cell above and to the left of the one that
                # changed.
                row = int(address.get(f"{TABLE}row", "0")) + 1
                column = int(address.get(f"{TABLE}column", "0")) + 1
                table = int(address.get(f"{TABLE}table", "0"))
            except ValueError:
                continue
            author, date = _change_info(change)
            changes.append(
                CellChange(
                    sheet=names[table] if 0 <= table < len(names) else "(unnamed)",
                    row=row,
                    column=column,
                    previous=_previous_value(change),
                    author=author,
                    date=date,
                )
            )

        for deletion in tracked.iter(f"{TABLE}deletion"):
            author, date = _change_info(deletion)
            kind = deletion.get(f"{TABLE}type") or "region"
            where = deletion.get(f"{TABLE}position") or "an unstated position"
            try:
                table = int(deletion.get(f"{TABLE}table", "0"))
            except ValueError:
                table = 0
            # LibreOffice writes the author, the date and the position, and no
            # cells at all. A finding that quotes nothing teaches a reader to
            # skip findings, so this is remarked on and counted into the
            # history rather than reported.
            deletions.append(
                TrackedDeletion(
                    sheet=names[table] if 0 <= table < len(names) else "(unnamed)",
                    where=f"{kind} {where}",
                    author=author,
                    date=date,
                )
            )
            remarks.append(
                f"a tracked {kind} deletion at position {where} by "
                f"{author or 'an editor the file does not name'} carries no "
                "content in this file, so there is nothing to quote"
            )
    return changes, deletions, remarks


def read_sheets(archive: zipfile.ZipFile) -> tuple[SheetRecord, tuple[Comment, ...]]:
    if "content.xml" not in archive.namelist():
        return SheetRecord(remarks=("the file has no content.xml and was not read",)), ()

    try:
        root = ElementTree.fromstring(archive.read("content.xml"))
    except ElementTree.ParseError as exc:
        return SheetRecord(remarks=(f"content.xml is not well-formed XML: {exc}",)), ()

    invisible = _hidden_sheet_styles(root)

    sheets: list[Sheet] = []
    comments: list[Comment] = []
    for body in root.iter(f"{OFFICE}spreadsheet"):
        for table in body.iter(f"{TABLE}table"):
            style = table.get(f"{TABLE}style-name")
            sheet, found = _read_table(table, "hidden" if style in invisible else None)
            sheets.append(sheet)
            comments.extend(found)

    # After the sheets, because a change names its table by index and the
    # report has to give a reader a name they can act on.
    changes, deletions, remarks = _read_tracked_changes(root, [s.name for s in sheets])

    return (
        SheetRecord(
            sheets=tuple(sheets),
            changes=tuple(changes),
            deletions=tuple(deletions),
            remarks=tuple(remarks),
        ),
        tuple(comments),
    )
