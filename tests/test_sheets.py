"""Spreadsheets, in both families.

The specimen is one tender evaluation exported twice. It hides three things
three different ways - a column, a row and a whole sheet - and carries a cell
comment, which is a fourth. Nothing is drawn over anything and no character is
invisible: every value is in the file exactly as it was typed, beside an
attribute saying not to draw it.

What made this worth doing was not the missing feature. Pointed at the .ods,
`unmasker` used to print **nothing hidden found** and exit 0, having read the
hidden row, the hidden column and the hidden sheet as ordinary visible prose -
a spreadsheet fell through to the reader for text documents, because both are
a zip with a `content.xml` in it. That is the tool stating something the
evidence does not support, which is the one thing `CLAUDE.md` forbids outright,
and `test_the_hidden_values_are_not_read_as_visible_text` is the guard against
its return.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unmasker.cli import collect
from unmasker.readers import read
from unmasker.sheets import detect

SPECIMENS = Path(__file__).parent / "specimens"

XLSX = SPECIMENS / "xlsx" / "libreoffice-calc-hidden-columns.xlsx"
ODS = SPECIMENS / "ods" / "libreoffice-calc-hidden-columns.ods"

BOTH = pytest.mark.parametrize("specimen", [XLSX, ODS], ids=["xlsx", "ods"])

RESERVE = "Reserve price (EUR)"
WITHDRAWN = "Delta Consulting sp. z o.o."
WORKINGS = "Reserve set at 240,000."


def findings_for(specimen: Path):
    return collect(read(specimen))


def by_detector(specimen: Path, name: str):
    return [f for f in findings_for(specimen) if f.detector == name]


# --------------------------------------------------------------------------
# the reader tells a spreadsheet from a text document
# --------------------------------------------------------------------------


@BOTH
def test_the_reader_names_the_file_a_spreadsheet(specimen):
    assert read(specimen).kind == "spreadsheet"


@BOTH
def test_the_visible_cells_are_read_as_text(specimen):
    """The tier-2 character detectors run on whatever a reader yields, so the
    cells a person can see have to arrive as text."""
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert "Kowalski i Wspolnicy sp. z o.o." in shown
    assert "Technical" in shown


@BOTH
def test_the_hidden_values_are_not_read_as_visible_text(specimen):
    """The regression this whole module exists for.

    Reading a hidden row as body text does not merely miss a finding: it
    reports concealed content as though a reader could see it, and then says
    nothing was hidden.
    """
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert WITHDRAWN not in shown
    assert RESERVE not in shown
    assert WORKINGS not in shown


@BOTH
def test_a_spreadsheet_is_not_reported_as_clean(specimen):
    assert findings_for(specimen), "a file that hides three things reported nothing"


# --------------------------------------------------------------------------
# the hidden sheet
# --------------------------------------------------------------------------


@BOTH
def test_the_hidden_sheet_is_reported_once(specimen):
    (found,) = by_detector(specimen, "hidden-sheet")
    assert "Workings" in found.summary


@BOTH
def test_the_hidden_sheet_quotes_what_is_on_it(specimen):
    (found,) = by_detector(specimen, "hidden-sheet")
    assert WORKINGS in found.machine_reads


@BOTH
def test_the_visible_sheet_is_not_reported(specimen):
    (found,) = by_detector(specimen, "hidden-sheet")
    assert "Evaluation" not in found.summary


# --------------------------------------------------------------------------
# the hidden column and the hidden row
# --------------------------------------------------------------------------


@BOTH
def test_the_hidden_column_is_reported_with_its_letter(specimen):
    """`column D` is what the person who hid it saw. A zero-based index is
    this tool's number, not theirs, and a reader cannot act on it."""
    (found,) = by_detector(specimen, "hidden-columns")
    assert "column D" in found.summary


@BOTH
def test_the_hidden_column_quotes_every_value_in_it(specimen):
    (found,) = by_detector(specimen, "hidden-columns")
    for value in (RESERVE, "211000", "238000", "251000"):
        assert value in found.machine_reads


@BOTH
def test_the_hidden_row_is_reported_with_its_number(specimen):
    (found,) = by_detector(specimen, "hidden-rows")
    assert "row 4" in found.summary


@BOTH
def test_the_hidden_row_quotes_the_bidder_it_removed(specimen):
    (found,) = by_detector(specimen, "hidden-rows")
    assert WITHDRAWN in found.machine_reads


@BOTH
def test_the_hidden_row_names_its_sheet(specimen):
    (found,) = by_detector(specimen, "hidden-rows")
    assert "Evaluation" in found.summary


@BOTH
def test_the_value_hidden_twice_over_is_still_reported_once_per_axis(specimen):
    """The withdrawn bidder's reserve price sits in the hidden row *and* the
    hidden column. Two findings state it, because they are two answers to two
    questions - `CLAUDE.md` forbids ranking one against the other - and neither
    is allowed to suppress the other."""
    assert len(by_detector(specimen, "hidden-rows")) == 1
    assert len(by_detector(specimen, "hidden-columns")) == 1
    assert "196000" in by_detector(specimen, "hidden-rows")[0].machine_reads
    assert "196000" in by_detector(specimen, "hidden-columns")[0].machine_reads


# --------------------------------------------------------------------------
# the comment
# --------------------------------------------------------------------------


@BOTH
def test_the_cell_comment_is_reported(specimen):
    (found,) = by_detector(specimen, "comment")
    assert "Panel agreed the reserve" in found.machine_reads


@BOTH
def test_the_cell_comment_names_its_author(specimen):
    (found,) = by_detector(specimen, "comment")
    assert "Halina Probna-Test" in found.summary


# --------------------------------------------------------------------------
# what the report does with all of it
# --------------------------------------------------------------------------


@BOTH
def test_every_spreadsheet_detector_fires_on_a_file_a_producer_wrote(specimen):
    """The rule the PDF specimens established: a detector covered only by a
    hand-built fixture is exactly the shape of the bug that started this
    project."""
    fired = {f.detector for f in findings_for(specimen)}
    assert {"hidden-sheet", "hidden-rows", "hidden-columns", "comment"} <= fired


@BOTH
def test_nothing_visible_is_reported_as_hidden(specimen):
    """The other half. A bidder on the page must not appear in any finding's
    machine reading, or the tool is calling the visible document a
    concealment."""
    hiding = [
        f
        for f in findings_for(specimen)
        if f.detector in ("hidden-sheet", "hidden-rows", "hidden-columns")
    ]
    for found in hiding:
        assert "Nowak Systemy SA" not in found.machine_reads


@BOTH
def test_the_two_families_report_the_same_hiding(specimen):
    """One source document, two containers. The two state hiding differently -
    an attribute in OOXML, a style indirection in ODF for a whole sheet - and
    a reader that got either wrong would disagree with the other."""
    detectors = sorted(
        f.detector
        for f in findings_for(specimen)
        if f.detector in ("hidden-sheet", "hidden-rows", "hidden-columns", "comment")
    )
    assert detectors == ["comment", "hidden-columns", "hidden-rows", "hidden-sheet"]


# --------------------------------------------------------------------------
# the record, on its own
# --------------------------------------------------------------------------


@BOTH
def test_the_record_lists_every_sheet_including_the_visible_one(specimen):
    record = read(specimen).sheets
    assert [sheet.name for sheet in record.sheets] == ["Evaluation", "Workings"]


@BOTH
def test_a_record_with_nothing_hidden_produces_no_findings(specimen):
    from unmasker.sheets import SheetRecord

    assert detect(SheetRecord()) == []


# --------------------------------------------------------------------------
# what mutation testing asked for
#
# Every test below covers a claim a docstring already made and no test held to.
# The mutation harness broke each claim in turn and the suite stayed green.
# --------------------------------------------------------------------------

from unmasker.sheets import Cell, Sheet, SheetRecord, column_name  # noqa: E402


def sheet(**kwargs) -> SheetRecord:
    return SheetRecord(sheets=(Sheet(**kwargs),))


def test_a_hidden_row_inside_a_hidden_sheet_is_not_reported_twice():
    """The sheet is already the finding. Saying that row 2 of an invisible
    sheet is also invisible tells a reader nothing they did not just read."""
    record = sheet(
        name="Workings",
        hidden="hidden",
        cells=(Cell(row=2, column=1, text="buried"),),
        hidden_rows=frozenset({2}),
        hidden_columns=frozenset({1}),
    )
    assert [f.detector for f in detect(record)] == ["hidden-sheet"]


def test_a_hidden_row_with_nothing_in_it_is_not_reported():
    """A finding that quotes nothing teaches a reader to skip findings."""
    record = sheet(name="S", cells=(), hidden_rows=frozenset({7}))
    assert detect(record) == []


def test_a_hidden_sheet_with_nothing_on_it_is_not_reported():
    assert detect(sheet(name="Empty", hidden="hidden", cells=())) == []


def test_consecutive_hidden_rows_are_one_finding():
    """Hiding rows 4 to 6 is one act by one person. A finding per row is a
    report nobody finishes reading."""
    record = sheet(
        name="S",
        cells=tuple(Cell(row=r, column=1, text=f"v{r}") for r in (4, 5, 6)),
        hidden_rows=frozenset({4, 5, 6}),
    )
    (found,) = detect(record)
    assert "rows 4 to 6" in found.summary
    assert found.machine_reads == "v4 | v5 | v6"


def test_hidden_rows_that_are_not_consecutive_are_separate_findings():
    record = sheet(
        name="S",
        cells=tuple(Cell(row=r, column=1, text=f"v{r}") for r in (2, 9)),
        hidden_rows=frozenset({2, 9}),
    )
    assert sorted(f.summary.split(" of ")[0] for f in detect(record)) == ["row 2", "row 9"]


def test_column_letters_go_past_z():
    """26 columns is a small spreadsheet. `AA` has to be right or the report
    sends a reader to the wrong column, which is worse than silence."""
    assert [column_name(n) for n in (1, 26, 27, 28, 52, 53, 702, 703)] == [
        "A",
        "Z",
        "AA",
        "AB",
        "AZ",
        "BA",
        "ZZ",
        "AAA",
    ]


def test_a_very_hidden_sheet_says_it_cannot_be_undone():
    """`veryHidden` is not a stronger word for `hidden`. The spreadsheet's own
    interface offers no way to bring the sheet back, so a person who opens the
    workbook has no way of learning it is there.

    LibreOffice cannot set it in either format, so nothing in the specimens
    exercises this and only this test does.
    """
    record = sheet(name="Macro", hidden="very hidden", cells=(Cell(1, 1, "buried"),))
    (found,) = detect(record)
    assert "very hidden" in found.summary
    assert "no way to undo" in found.summary


# --------------------------------------------------------------------------
# the readers, on archives built for one question each
#
# Synthetic, and deliberately so: each of these isolates a producer behaviour
# the specimens carry only incidentally, or one no producer on this machine
# emits at all. The specimens remain the proof that the readers work; these
# are the proof that they work for the stated reason.
# --------------------------------------------------------------------------

import io  # noqa: E402
import zipfile  # noqa: E402

from unmasker.odf.sheets import read_sheets as read_odf_sheets  # noqa: E402
from unmasker.ooxml.sheets import read_sheets as read_ooxml_sheets  # noqa: E402


def archive(**parts: str) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as writing:
        for name, body in parts.items():
            writing.writestr(name.replace("__", "/").replace("_x_", "."), body)
    return zipfile.ZipFile(buffer)


def workbook(sheet_xml: str, shared: str = "", sheets: str = "") -> zipfile.ZipFile:
    return archive(
        **{
            "xl__workbook_x_xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                "<sheets>"
                + (sheets or '<sheet name="S" sheetId="1" state="visible" r:id="rId1"/>')
                + "</sheets></workbook>"
            ),
            "xl___rels__workbook_x_xml_x_rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
            "xl__worksheets__sheet1_x_xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + sheet_xml
                + "</worksheet>"
            ),
            "xl__sharedStrings_x_xml": (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + shared
                + "</sst>"
            ),
        }
    )


def content(body: str, styles: str = "") -> zipfile.ZipFile:
    return archive(
        **{
            "content_x_xml": (
                '<office:document-content'
                ' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
                ' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
                ' xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
                ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
                ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f"<office:automatic-styles>{styles}</office:automatic-styles>"
                f"<office:body><office:spreadsheet>{body}</office:spreadsheet></office:body>"
                "</office:document-content>"
            )
        }
    )


def cell(text: str, repeated: int = 1) -> str:
    span = f' table:number-columns-repeated="{repeated}"' if repeated > 1 else ""
    return f'<table:table-cell{span}><text:p>{text}</text:p></table:table-cell>'


def test_one_col_element_hides_the_whole_range_it_names():
    """`min` and `max` are a range, not an identifier. Excel writes one element
    for a whole selection, so reading only `min` reports the first column and
    loses every other one."""
    record, _ = read_ooxml_sheets(
        workbook(
            '<cols><col min="2" max="4" hidden="true"/></cols>'
            '<sheetData><row r="1">'
            '<c r="A1" t="inlineStr"><is><t>keep</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>b</t></is></c>'
            '<c r="C1" t="inlineStr"><is><t>c</t></is></c>'
            '<c r="D1" t="inlineStr"><is><t>d</t></is></c>'
            "</row></sheetData>"
        )
    )
    (found,) = detect(record)
    assert "columns B to D" in found.summary
    assert found.machine_reads == "b | c | d"


def test_a_shared_string_split_across_runs_comes_back_whole():
    """A string is split into several `t` elements wherever part of it is
    formatted differently. Taking the first returns a fragment, and a report
    that quotes a fragment of a concealed value has understated it."""
    record, _ = read_ooxml_sheets(
        workbook(
            '<sheetData><row r="2" hidden="true"><c r="A2" t="s"><v>0</v></c></row></sheetData>',
            shared="<si><r><t>the reserve is </t></r><r><t>240,000</t></r></si>",
        )
    )
    (found,) = detect(record)
    assert found.machine_reads == "the reserve is 240,000"


def test_a_row_the_workbook_lists_without_a_part_is_remarked_on():
    """Searched and found nothing is not the same answer as there was nothing
    to search, and a reader must not be handed the first for the second."""
    record, _ = read_ooxml_sheets(
        workbook(
            "<sheetData/>",
            sheets=(
                '<sheet name="S" sheetId="1" r:id="rId1"/>'
                '<sheet name="Gone" sheetId="2" r:id="rId9"/>'
            ),
        )
    )
    assert any("Gone" in remark and "missing" in remark for remark in record.remarks)


def test_a_repeated_row_advances_the_row_number():
    """ODF writes no row number. A run of identical rows stands in for each of
    them, and a reader that counts it as one reports every later row under a
    number the person who hid it would not recognise."""
    record, _ = read_odf_sheets(
        content(
            '<table:table table:name="S">'
            "<table:table-column/>"
            f'<table:table-row table:number-rows-repeated="3">{cell("filler")}</table:table-row>'
            f'<table:table-row table:visibility="collapse">{cell("buried")}</table:table-row>'
            "</table:table>"
        )
    )
    (found,) = detect(record)
    assert "row 4" in found.summary


def test_a_repeated_cell_advances_the_column_number():
    record, _ = read_odf_sheets(
        content(
            '<table:table table:name="S">'
            "<table:table-column/>"
            '<table:table-column table:number-columns-repeated="2"/>'
            '<table:table-column table:visibility="collapse"/>'
            f'<table:table-row>{cell("filler", repeated=3)}{cell("buried")}</table:table-row>'
            "</table:table>"
        )
    )
    (found,) = detect(record)
    assert "column D" in found.summary
    assert found.machine_reads == "buried"


def test_a_comment_inside_a_cell_is_not_the_value_of_the_cell():
    """The trap `readers/odf.py` documents for annotations in a paragraph,
    one container down. Walking the subtree naively reports the comment as the
    number in the cell."""
    record, comments = read_odf_sheets(
        content(
            '<table:table table:name="S">'
            "<table:table-column/>"
            '<table:table-row table:visibility="collapse"><table:table-cell>'
            "<office:annotation><dc:creator>H. Probna</dc:creator>"
            "<text:p>ask before sending</text:p></office:annotation>"
            "<text:p>196000</text:p>"
            "</table:table-cell></table:table-row>"
            "</table:table>"
        )
    )
    (found,) = detect(record)
    assert found.machine_reads == "196000"
    assert [c.text for c in comments] == ["ask before sending"]


def test_a_visibility_value_that_is_not_hiding_is_not_read_as_hiding():
    """`table:visibility` takes `visible` too, and a reader that treats any
    value as concealment reports the whole sheet."""
    record, _ = read_odf_sheets(
        content(
            '<table:table table:name="S">'
            "<table:table-column/>"
            f'<table:table-row table:visibility="visible">{cell("on the screen")}</table:table-row>'
            "</table:table>"
        )
    )
    assert detect(record) == []


def test_an_ods_with_no_spreadsheet_body_yields_no_sheets():
    record, _ = read_odf_sheets(archive(**{"content_x_xml": "<office:document/>"}))
    assert record.sheets == ()


# --------------------------------------------------------------------------
# rows a filter is holding back
# --------------------------------------------------------------------------

FILTERED = SPECIMENS / "ods" / "libreoffice-calc-filtered-rows.ods"


def test_filtered_rows_are_reported():
    (found,) = [f for f in collect(read(FILTERED)) if f.detector == "filtered-rows"]
    assert "KZ-2023-0912" in found.machine_reads
    assert "KZ-2023-0948" in found.machine_reads


def test_filtered_rows_are_circumstantial_not_direct():
    """A filter is a live working state. The rows come back when it is cleared
    and whoever is looking at the screen set it, so it is consistent with
    concealment and with an ordinary afternoon's work."""
    from unmasker.findings import Basis

    (found,) = [f for f in collect(read(FILTERED)) if f.detector == "filtered-rows"]
    assert found.basis is Basis.CIRCUMSTANTIAL
    assert "filter" in found.summary


def test_filtered_rows_are_not_also_reported_as_hidden():
    """Two names for one row would be the same value counted twice, which is
    the report telling a reader there is more here than there is."""
    assert [f for f in collect(read(FILTERED)) if f.detector == "hidden-rows"] == []


def test_the_open_cases_are_still_read_as_visible_text():
    shown = "\n".join(unit.text for unit in read(FILTERED).units)
    assert "KZ-2024-0031" in shown
    assert "KZ-2023-0912" not in shown


def test_a_row_that_is_both_hidden_and_filtered_is_reported_once_as_hidden():
    """No reader here can produce one - ODF gives a row a single `visibility`
    and SpreadsheetML records no filtering at all - but `Sheet` is a public
    record and the precedence has to be stated somewhere. The stronger claim
    is the one reported, and it is reported once: two names for one row would
    be the report telling a reader there is more here than there is.
    """
    record = sheet(
        name="S",
        cells=(Cell(row=3, column=1, text="buried"),),
        hidden_rows=frozenset({3}),
        filtered_rows=frozenset({3}),
    )
    assert [f.detector for f in detect(record)] == ["hidden-rows"]


# --------------------------------------------------------------------------
# a stored value is not always the value on the screen
#
# ODF keeps the formatted text in the cell's paragraph, so the two agree there
# and the reader needs to do nothing. SpreadsheetML keeps only the number and a
# style index, so a hidden column of dates reads as `45366 | 45397` unless the
# number format is resolved - which is a quotation the person who hid it would
# not recognise, and worse than useless in a report.
# --------------------------------------------------------------------------

FORMATTED = SPECIMENS / "xlsx" / "libreoffice-calc-formatted-values.xlsx"
FORMATTED_ODS = SPECIMENS / "ods" / "libreoffice-calc-formatted-values.ods"

FORMATS = pytest.mark.parametrize("specimen", [FORMATTED, FORMATTED_ODS], ids=["xlsx", "ods"])


@FORMATS
def test_a_hidden_date_is_reported_as_a_date(specimen):
    """Stored as 45366, shown as a date, and both families must say the date.
    A serial number is the file's arithmetic, not the document's content."""
    (found,) = by_detector(specimen, "hidden-rows")
    assert "2024-03-15" in found.machine_reads
    assert "45366" not in found.machine_reads


def test_a_hidden_currency_value_keeps_the_number_the_xlsx_stores():
    """The other half of the same decision. Rendering `#,###.00" zl"` means
    writing a number formatter, and one that is nearly right would quote a
    figure that is nearly right - so the stored number is quoted, which is
    exact, and the format is named in a note."""
    (found,) = by_detector(FORMATTED, "hidden-rows")
    assert "240000" in found.machine_reads


def test_the_ods_quotes_the_currency_the_way_the_sheet_shows_it():
    """Not an inconsistency between the readers: an inconsistency between the
    formats, reported faithfully. ODF keeps the formatted text in the cell, so
    there is a displayed value to quote and the tool quotes it. OOXML keeps
    only the number, so there is not.

    The tool says what each file says. Making the .ods quote `240000` to match
    the .xlsx would be throwing away evidence one of them actually carries.
    """
    (found,) = by_detector(FORMATTED_ODS, "hidden-rows")
    assert "240" in found.machine_reads and "00,00 zl" in found.machine_reads
    assert "240000" not in found.machine_reads


def test_the_note_names_the_format_the_sheet_applies():
    """`CLAUDE.md`: nothing found has two meanings, and so does a value that
    does not match what a reader saw. The note says the quotation is the stored
    value and what the sheet does to it."""
    remarks = read(FORMATTED).remarks
    assert any("zl" in remark and "as stored" in remark for remark in remarks)


def test_a_general_cell_produces_no_note():
    """A note on every workbook is a note nobody reads."""
    assert not [r for r in read(XLSX).remarks if "as stored" in r]


def test_a_date_needs_no_note_because_it_was_rendered():
    remarks = read(FORMATTED).remarks
    assert not any("yyyy" in remark for remark in remarks)


def test_the_two_families_agree_about_the_hidden_date():
    """One source document. The .ods carries the formatted text and the .xlsx
    carries a serial number, and a reader that got the second wrong would
    disagree with the first about what the file says."""
    xlsx = by_detector(FORMATTED, "hidden-rows")[0].machine_reads
    ods = by_detector(FORMATTED_ODS, "hidden-rows")[0].machine_reads
    assert "2024-03-15" in xlsx and "2024-03-15" in ods


# --------------------------------------------------------------------------
# number formats no producer on this machine writes
#
# LibreOffice defines every format explicitly, exports `date1904="false"`, and
# was not asked for a time of day. Each of these is the behaviour the specimen
# notes name as missing, held by a test rather than by nothing.
# --------------------------------------------------------------------------

from unmasker.ooxml.sheets import EPOCH as EPOCH_DEFAULT  # noqa: E402
from unmasker.ooxml.sheets import _as_date, _is_date_format  # noqa: E402


def dated(sheet_xml: str, styles: str, workbook_pr: str = "") -> zipfile.ZipFile:
    return archive(
        **{
            "xl__workbook_x_xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                + workbook_pr
                + '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>'
            ),
            "xl___rels__workbook_x_xml_x_rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'
            ),
            "xl__worksheets__sheet1_x_xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + sheet_xml
                + "</worksheet>"
            ),
            "xl__styles_x_xml": (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + styles
                + "</styleSheet>"
            ),
        }
    )


HIDDEN_NUMBER = (
    '<sheetData><row r="1" hidden="true">'
    '<c r="A1" s="0"><v>{}</v></c></row></sheetData>'
)


def test_a_built_in_date_format_is_recognised_without_a_format_code():
    """`numFmtId` 14 to 22 and 45 to 47 are dates, and the file does not write
    their codes down because every reader is expected to know them. Excel
    routinely uses them; LibreOffice defines its own instead, so nothing here
    produces one."""
    record, _ = read_ooxml_sheets(
        dated(
            HIDDEN_NUMBER.format("45366"),
            '<cellXfs><xf numFmtId="14"/></cellXfs>',
        )
    )
    (found,) = detect(record)
    assert found.machine_reads == "2024-03-15"


def test_a_date_letter_inside_a_quoted_literal_is_not_a_date():
    """`0.00" days"` is a number with a unit after it, and the unit is spelled
    with the letters of a date. Testing the raw format code calls it a date and
    renders the number as one - a quotation that is not merely imprecise but a
    different kind of thing.

    The literal has to contain a *real* token to discriminate. An earlier
    version of this test used `0.00"m"`, which passes whether or not the
    quoting is honoured, because `m` alone is ambiguous between month and
    minute and is deliberately not a token on its own. Mutation testing caught
    it passing for the wrong reason.
    """
    assert not _is_date_format(0, '0.00" days"')
    assert not _is_date_format(0, '#,##0" hours"')
    assert not _is_date_format(0, "0.00\\d")
    assert _is_date_format(0, "yyyy\\-mm\\-dd")


def test_a_workbook_that_counts_from_1904_is_read_that_way():
    """A four-year-and-a-day error, silent, on every date in the file."""
    record, _ = read_ooxml_sheets(
        dated(
            HIDDEN_NUMBER.format("43904"),
            '<cellXfs><xf numFmtId="14"/></cellXfs>',
            workbook_pr='<workbookPr date1904="true"/>',
        )
    )
    (found,) = detect(record)
    assert found.machine_reads == "2024-03-15"


def test_the_same_serial_without_the_1904_flag_is_a_different_day():
    """The other half: the flag has to change the answer, or reading it proves
    nothing."""
    record, _ = read_ooxml_sheets(
        dated(HIDDEN_NUMBER.format("43904"), '<cellXfs><xf numFmtId="14"/></cellXfs>')
    )
    (found,) = detect(record)
    assert found.machine_reads == "2020-03-14"


def test_a_time_of_day_is_rendered_beside_the_date():
    """A serial's fractional part is the time. It is only shown where the
    format asks for one - a date-only format on a value with a fraction is a
    cell whose time the sheet does not display."""
    assert _as_date("45366.5", "yyyy-mm-dd hh:mm", EPOCH_DEFAULT) == "2024-03-15 12:00"
    assert _as_date("45366.5", "yyyy-mm-dd", EPOCH_DEFAULT) == "2024-03-15"


def test_a_value_that_is_not_a_number_is_not_forced_into_a_date():
    assert _as_date("not a serial", "yyyy-mm-dd", EPOCH_DEFAULT) is None
