"""Change tracking in a spreadsheet: the previous value of a cell.

A bid edited from 240 000 down to 198 000 still holds the 240 000, beside the
name of whoever changed it and the minute they did. It is `w:delText` again,
arriving through a container that has cells instead of paragraphs - and unlike
a Word deletion, this one has a *current* value to sit beside, so both columns
of the report carry real text. It is the only finding in the project where
`human sees` is a value rather than an absence.

Both families carry all of it, by different routes. ODF keeps a
`<table:tracked-changes>` block at the top of the spreadsheet body; OOXML keeps
`xl/revisions/`, which is the shared-workbook revision log - one header per
editing session, each pointing at its own log part. A first look at only
`revisionLog1.xml` suggested the .xlsx export was lossy. It is not: there were
three log parts, and the second and third held the change and the deletion the
first did not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unmasker.cli import collect
from unmasker.findings import Basis
from unmasker.readers import read

SPECIMENS = Path(__file__).parent / "specimens"

ODS = SPECIMENS / "ods" / "libreoffice-calc-tracked-changes.ods"
XLSX = SPECIMENS / "xlsx" / "libreoffice-calc-tracked-changes.xlsx"

BOTH = pytest.mark.parametrize("specimen", [ODS, XLSX], ids=["ods", "xlsx"])

WAS_OFFER = "240000"
NOW_OFFER = "198000"
WAS_NOTE = "rejected on price"


def changes(specimen: Path):
    return [f for f in collect(read(specimen)) if f.detector == "changed-cell"]


# --------------------------------------------------------------------------
# what both families carry
# --------------------------------------------------------------------------


@BOTH
def test_the_earlier_figure_is_reported(specimen):
    found = next(f for f in changes(specimen) if WAS_OFFER in f.machine_reads)
    assert found.basis is Basis.DIRECT


@BOTH
def test_the_finding_fills_both_of_its_columns(specimen):
    """Almost every container finding leaves `human sees` empty, because the
    hidden text has nothing on the page to sit beside. A changed cell does:
    the reader is looking at 198 000 while the file also holds 240 000."""
    found = next(f for f in changes(specimen) if WAS_OFFER in f.machine_reads)
    assert found.human_sees == NOW_OFFER
    assert found.machine_reads == WAS_OFFER


@BOTH
def test_the_change_is_addressed_the_way_the_editor_saw_it(specimen):
    """`cell B2`, not row 1 column 1. ODF counts both from zero and the report
    must not pass that on to a reader who would then look at the wrong cell."""
    found = next(f for f in changes(specimen) if WAS_OFFER in f.machine_reads)
    assert "cell B2" in found.summary
    assert "Bids" in found.summary


@BOTH
def test_the_change_names_who_made_it_and_when(specimen):
    found = next(f for f in changes(specimen) if WAS_OFFER in f.machine_reads)
    assert "Halina Probna-Test" in found.summary
    assert "2024-06-12" in found.summary


@BOTH
def test_the_editors_are_still_reported_once_for_the_whole_file(specimen):
    """A change history is one fact about a document, not one fact per change -
    the same rule the DOCX reader follows, in a different container."""
    history = [f for f in collect(read(specimen)) if f.detector == "revision-history"]
    assert len(history) == 1
    assert history[0].basis is Basis.SELF_REPORTED


# --------------------------------------------------------------------------
# the previous value, in each of the two shapes a producer writes it
# --------------------------------------------------------------------------


@BOTH
def test_a_previous_value_that_is_text_is_read_as_well_as_one_that_is_a_number(specimen):
    """The producer fact this specimen exists for, and each family states it a
    different way. In ODF, LibreOffice writes a numeric previous value as
    `office:value` and *strips* the paragraph, and a string one as a paragraph
    with no `office:value` at all. In OOXML the same pair is `t="n"` with a
    `<v>`, against `t="inlineStr"` with an `<is>`. A reader that knows one form
    reads half the changes and then reports the file as though that were all of
    them."""
    found = next(f for f in changes(specimen) if f.machine_reads == WAS_NOTE)
    assert "cell C2" in found.summary
    assert found.human_sees == "shortlisted"


@BOTH
def test_both_changes_are_reported(specimen):
    assert len(changes(specimen)) == 2


@BOTH
def test_a_tracked_row_deletion_is_counted_and_not_quoted(specimen):
    """LibreOffice writes the author, the date and the position of a deleted
    row, and no cells at all. A finding that quotes nothing teaches a reader to
    skip findings, so it is remarked on and counted into the history instead."""
    extraction = read(specimen)
    assert any("no content" in remark for remark in extraction.remarks)
    history = next(f for f in collect(extraction) if f.detector == "revision-history")
    assert "deletion" in history.summary


@BOTH
def test_the_second_editor_is_named_in_the_history(specimen):
    history = next(f for f in collect(read(specimen)) if f.detector == "revision-history")
    assert "Piotr Przyklad" in history.machine_reads


# --------------------------------------------------------------------------
# the revision log, which is not to be believed about the present
# --------------------------------------------------------------------------


def test_every_log_part_is_read_and_not_only_the_first():
    """`xl/revisions/` is one header per editing session, each pointing at its
    own log part through a relationship. A reader that opened
    `revisionLog1.xml` and stopped would report one change out of three and
    give no sign it had stopped - which is what a first look at this file
    suggested was the export losing them."""
    import zipfile

    with zipfile.ZipFile(XLSX) as archive:
        parts = [n for n in archive.namelist() if "revisionLog" in n]
    assert len(parts) == 3, "the specimen no longer exercises multiple log parts"
    assert len(changes(XLSX)) == 2


def test_the_current_value_comes_from_the_sheet_and_not_the_revision_log():
    """LibreOffice writes `<nc>` holding the *old* value rather than the
    current one. Trusting the log would report a cell that changed from 240000
    to 240000, which is a finding that contradicts itself on its own line."""
    found = next(f for f in changes(XLSX) if f.machine_reads == WAS_OFFER)
    assert found.human_sees == NOW_OFFER


# --------------------------------------------------------------------------
# the visible sheet is still the visible sheet
# --------------------------------------------------------------------------


@BOTH
def test_the_current_values_are_still_read_as_visible_text(specimen):
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert NOW_OFFER in shown
    assert "Nowak Systemy SA" in shown


@BOTH
def test_no_previous_value_leaks_into_the_visible_text(specimen):
    """A previous value is not on the sheet. Yielding it as body text would
    hand it to the character detectors as though a person could see it."""
    shown = "\n".join(unit.text for unit in read(specimen).units)
    assert WAS_NOTE not in shown


# --------------------------------------------------------------------------
# what mutation testing asked for
# --------------------------------------------------------------------------


def test_a_change_that_replaced_nothing_is_not_reported():
    """A cell that was empty and got filled has a tracked change with no
    previous value. Reporting it would put an entry in the report whose
    machine reading is `nothing in the file`, and a finding that quotes
    nothing teaches a reader to skip findings."""
    from unmasker.sheets import Cell, CellChange, Sheet, SheetRecord, detect

    record = SheetRecord(
        sheets=(Sheet(name="Bids", cells=(Cell(row=2, column=2, text="198000"),)),),
        changes=(
            CellChange(
                sheet="Bids", row=2, column=2, previous="", author="H", date="2024-06-12"
            ),
        ),
    )
    assert detect(record) == []


@BOTH
def test_a_changed_cell_is_not_also_reported_as_deleted_text(specimen):
    """The two findings would quote the same value under two names, and a
    reader counting findings would think the file gave up more than it did.

    `deleted-text` is for text a revision took off the page and left in the
    file with nothing in its place. A changed cell has something in its place -
    that is the whole shape of the finding - so it is reported by
    `changed-cell` and by nothing else.
    """
    found = collect(read(specimen))
    assert not [f for f in found if f.detector == "deleted-text"]
    assert [f for f in found if f.detector == "changed-cell"]
