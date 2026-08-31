# libreoffice-calc-hidden-columns.ods

The same tender evaluation as
[`xlsx/libreoffice-calc-hidden-columns.xlsx`](../xlsx/libreoffice-calc-hidden-columns.md),
written in the other family. A hidden column, a hidden row, a hidden sheet and
a cell comment.

- 12 158 bytes
- produced by LibreOffice 24.2 Calc, in its own format

## How it was made

```bash
python3 tests/specimens/sources/build_calc_hidden_columns.py \
    tests/specimens/xlsx/libreoffice-calc-hidden-columns.xlsx \
    tests/specimens/ods/libreoffice-calc-hidden-columns.ods
```

## What a human sees

The same thing the .xlsx shows: one sheet, columns A B C E F, rows 1 2 3 5.

## What is actually in the file

| | | |
| --- | --- | --- |
| style `hidden-sheet`, `table:display="false"` | sheet `Workings` | `Reserve set at 240,000. Kowalski came in 12% under; the others were told nothing.` |
| `table:visibility="collapse"` on the column | column D of `Evaluation` | `Reserve price (EUR)`, `211000`, `238000`, `196000`, `251000` |
| `table:visibility="collapse"` on the row | row 4 of `Evaluation` | `Delta Consulting sp. z o.o.`, `82`, `44`, `196000`, `63`, `withdrawn after the deadline - do not list` |
| `<office:annotation>` inside cell F2 | Halina Probna-Test, 2024-06-11 | `Panel agreed the reserve before the bids were opened. Not for the file we release.` |

## What it is for

**This is the file that showed the bug worth fixing.** Pointed at it,
`unmasker` printed

```text
searched the text of this file. Nothing hidden found by the detectors that exist.
```

and exited 0 — having read the hidden row, the hidden column and the whole
hidden sheet as ordinary visible prose. An .ods is a zip with a `content.xml`
in it, which is also the description of an .odt, so it went to the reader for
text documents and that reader has no concept of a row nobody can see. Not a
missing feature: the tool stated something the evidence does not support, which
`CLAUDE.md` names as the one thing it must never do.
`test_the_hidden_values_are_not_read_as_visible_text` is the guard against its
return.

**A whole sheet's visibility is behind an indirection**, and it is the reason
the ODF reader is not a translation of the OOXML one. SpreadsheetML writes
`state="hidden"` on the sheet. ODF writes nothing on the sheet at all: the
table names a style, and the style, elsewhere in the file, says
`table:display="false"`. A reader that looks for an attribute finds none and
reports a workbook with a concealed sheet as clean.

**A producer fact, measured.** The first attempt at this specimen hid the
column with `table:display="false"` on a column style, which is what the ODF
specification suggests. LibreOffice **silently dropped it** — in both exports.
The form that round-trips is `table:visibility="collapse"` on the column
itself. A fixture built from the specification would have hidden nothing and
the test suite would have been green about it, which is the `filetrail` HEIC
bug wearing new clothes.

**A cell address has to be counted.** ODF writes no `r="D4"`. Position comes
from document order, through `table:number-columns-repeated` and
`table:covered-table-cell`, and getting it wrong reports the right value under
the wrong letter — which is worse than not reporting it, because a reader
would go and look at the wrong column.

**The repeats run to the edge of the sheet.** LibreOffice closes this table
with rows repeated to row 1 048 576. Materialising that is a million-entry set
holding no information, so hidden ranges are resolved against the rows that
actually carry a value.

**A comment is inside the cell it annotates**, and its text is not the cell's
text. A reader that walks the subtree naively reports
`Panel agreed the reserve…` as the *value* of cell F2 — the same trap
`readers/odf.py` documents for annotations in a paragraph, one container down.

## What this specimen does not carry

- **A sheet marked very hidden.** ODF has no equivalent of `veryHidden` at
  all; it is a SpreadsheetML idea, and LibreOffice cannot set it in either
  format.
- **A filtered row**, which is a weaker claim than a hidden one. It has its own
  specimen: [`libreoffice-calc-filtered-rows.ods`](libreoffice-calc-filtered-rows.md).
- **Tracked changes.** ODF spreadsheets carry `table:tracked-changes` with
  cell-content changes in it, and nothing here reads or tests one.
- **A row group hidden as a group** rather than row by row.
