"""Hidden sheets, rows and columns, and what to report about them.

A spreadsheet conceals differently from every other container this tool reads.
There is no geometry, no invisible character and no tracked change. A row, a
column or an entire sheet carries an attribute saying not to draw it, and every
value in it stays in the file exactly as typed. Someone selects three columns,
right-clicks, chooses Hide, and sends the workbook out believing the numbers
are gone.

Hiding is not an OOXML idea and not an ODF one. Excel writes `hidden="true"`
on the row; LibreOffice writes `table:visibility="collapse"`; for a whole sheet
one writes `state="hidden"` on the sheet and the other points at a style that
says `table:display="false"`. All four are the same statement about a document:
*this is in the file and not on the screen.* So the record and the findings
live here, and each format contributes only a reader that fills the record in -
the arrangement `revisions.py` already uses for tracked changes.

Three rules decide the shape of what gets reported.

**A run of hidden rows is one finding, not one per row.** Hiding rows 10 to 40
is one act by one person, and both formats express it as a range anyway. A
finding per row is the `filetrail` lesson about a report nobody finishes,
arriving from a new direction.

**Rows and columns inside a hidden sheet are not reported.** The sheet is
already the finding. Saying that row 4 of an invisible sheet is also invisible
tells a reader nothing they did not just read.

**A filtered row is not the same claim as a hidden one.** A filter is a live
working state - the rows come back when it is cleared, and the person looking
at the screen knows they set it. It is still text in the file that is not on
the screen, so it is still reported, but as `circumstantial`: consistent with
concealment and with an ordinary afternoon's work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .findings import Basis, Finding, Location


@dataclass(frozen=True)
class Cell:
    """One cell's displayed text, and where it sits. Both 1-based, because
    `row 4` and `column D` are what the person who hid it saw. A zero-based
    index is this tool's number and a reader cannot act on it."""

    row: int
    column: int
    text: str


@dataclass(frozen=True)
class Sheet:
    name: str

    hidden: str | None = None
    """`None`, `hidden`, or `very hidden`.

    The third is not a stronger word for the second. A sheet marked
    `veryHidden` cannot be brought back through the spreadsheet's own interface
    at all - it takes a macro, or an editor pointed at the XML - so a person
    who opens the workbook has no way of learning it is there.
    """

    cells: tuple[Cell, ...] = ()
    hidden_rows: frozenset[int] = field(default_factory=frozenset)
    hidden_columns: frozenset[int] = field(default_factory=frozenset)
    filtered_rows: frozenset[int] = field(default_factory=frozenset)

    def text_of_row(self, row: int) -> tuple[str, ...]:
        return tuple(c.text for c in self.cells if c.row == row and c.text.strip())

    def text_of_column(self, column: int) -> tuple[str, ...]:
        return tuple(c.text for c in self.cells if c.column == column and c.text.strip())

    @property
    def visible_text(self) -> str:
        """What a person looking at this sheet reads, one row per line.

        The rows and columns an application has agreed not to draw are left
        out, which is the whole reason a spreadsheet needs its own reader:
        yielding every cell would hand the concealed values to the text
        detectors as though they were on the page, and then report that
        nothing was hidden.
        """
        if self.hidden:
            return ""
        rows: dict[int, list[str]] = {}
        for cell in self.cells:
            if cell.row in self.hidden_rows or cell.row in self.filtered_rows:
                continue
            if cell.column in self.hidden_columns:
                continue
            rows.setdefault(cell.row, []).append(cell.text)
        return "\n".join("\t".join(rows[r]) for r in sorted(rows))


@dataclass(frozen=True)
class SheetRecord:
    sheets: tuple[Sheet, ...] = ()
    remarks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.sheets


def column_name(index: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA. The address the person who hid it saw."""
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _runs(numbers: set[int]) -> list[tuple[int, int]]:
    """Consecutive numbers, collapsed into ranges.

    Hiding a block of rows is one act; reporting it as forty findings is a
    report nobody reads to the end.
    """
    out: list[tuple[int, int]] = []
    for number in sorted(numbers):
        if out and number == out[-1][1] + 1:
            out[-1] = (out[-1][0], number)
        else:
            out.append((number, number))
    return out


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _range_words(first: int, last: int, noun: str, name=str) -> str:
    if first == last:
        return f"{noun} {name(first)}"
    return f"{noun}s {name(first)} to {name(last)}"


def hidden_sheets(record: SheetRecord) -> list[Finding]:
    """Whole sheets the workbook carries and does not show."""
    findings = []
    for sheet in record.sheets:
        if not sheet.hidden:
            continue
        values = tuple(c.text for c in sheet.cells if c.text.strip())
        if not values:
            # A hidden sheet with nothing on it conceals nothing. Reporting it
            # would put an entry in the report whose machine reading is empty,
            # and a finding that quotes nothing teaches a reader to skip
            # findings.
            continue
        how = (
            "marked very hidden, which the spreadsheet's own interface offers "
            "no way to undo"
            if sheet.hidden == "very hidden"
            else "marked hidden"
        )
        findings.append(
            Finding(
                detector="hidden-sheet",
                basis=Basis.DIRECT,
                summary=(
                    f'sheet "{sheet.name}" is {how}, and holds '
                    f"{_plural(len(values), 'value')} still in the file"
                ),
                human_sees="",
                machine_reads=" | ".join(values),
                location=Location(),
            )
        )
    return findings


def _axis(
    record: SheetRecord,
    detector: str,
    noun: str,
    indices,
    values_of,
    name=str,
    basis: Basis = Basis.DIRECT,
    how: str = "hidden",
) -> list[Finding]:
    findings = []
    for sheet in record.sheets:
        if sheet.hidden:
            # The sheet is already the finding. Naming its hidden rows as well
            # tells a reader nothing they did not just read.
            continue
        for first, last in _runs(set(indices(sheet))):
            values: list[str] = []
            for index in range(first, last + 1):
                values.extend(values_of(sheet, index))
            if not values:
                continue
            where = _range_words(first, last, noun, name)
            verb = "is" if first == last else "are"
            findings.append(
                Finding(
                    detector=detector,
                    basis=basis,
                    summary=(
                        f'{where} of sheet "{sheet.name}" {verb} {how}, and '
                        f"{'holds' if first == last else 'hold'} "
                        f"{_plural(len(values), 'value')} still in the file"
                    ),
                    human_sees="",
                    machine_reads=" | ".join(values),
                    location=Location(),
                )
            )
    return findings


def hidden_rows(record: SheetRecord) -> list[Finding]:
    return _axis(
        record,
        "hidden-rows",
        "row",
        lambda sheet: sheet.hidden_rows,
        lambda sheet, index: sheet.text_of_row(index),
    )


def filtered_rows(record: SheetRecord) -> list[Finding]:
    """Rows a filter is holding back rather than a person hiding them."""
    return _axis(
        record,
        "filtered-rows",
        "row",
        lambda sheet: sheet.filtered_rows - sheet.hidden_rows,
        lambda sheet, index: sheet.text_of_row(index),
        basis=Basis.CIRCUMSTANTIAL,
        how="held back by a filter, which a reader of the file cannot see was set",
    )


def hidden_columns(record: SheetRecord) -> list[Finding]:
    return _axis(
        record,
        "hidden-columns",
        "column",
        lambda sheet: sheet.hidden_columns,
        lambda sheet, index: sheet.text_of_column(index),
        name=column_name,
    )


def detect(record: SheetRecord) -> list[Finding]:
    """Every spreadsheet finding in one workbook.

    Additive, and none outranks another. A value can sit in a hidden row *and*
    a hidden column, and both findings state it: they are two answers to two
    questions, and `CLAUDE.md` forbids ranking one against the other.
    """
    return (
        hidden_sheets(record) + hidden_rows(record) + hidden_columns(record) + filtered_rows(record)
    )
