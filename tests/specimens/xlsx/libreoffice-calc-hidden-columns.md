# libreoffice-calc-hidden-columns.xlsx

A tender evaluation with a hidden column, a hidden row, a hidden sheet and a
cell comment. Nothing is drawn over anything and no character is invisible:
every value is in the file exactly as it was typed, beside an attribute saying
not to draw it.

- 8 598 bytes
- produced by LibreOffice 24.2 Calc

Its sibling [`ods/libreoffice-calc-hidden-columns.ods`](../ods/libreoffice-calc-hidden-columns.md)
is the same source document exported to the other family. The pair exists
because the two state hiding *differently*, and a reader tried on one of them
would have a partial idea of what hiding is.

## How it was made

```bash
python3 tests/specimens/sources/build_calc_hidden_columns.py \
    tests/specimens/xlsx/libreoffice-calc-hidden-columns.xlsx \
    tests/specimens/ods/libreoffice-calc-hidden-columns.ods
```

Flat ODF, converted with `soffice --convert-to xlsx`. Checked before it was
committed: `state="hidden"`, `<col hidden="true">`, `<row hidden="true">` and
`xl/comments1.xml` all survive the ODF-to-OOXML conversion.

## What a human sees

Opening the workbook shows one sheet, `Evaluation`, with the columns running
A, B, C, E, F — nothing marks the gap where D was — and rows 1, 2, 3, 5:

```text
Bidder                            Technical  Price  Total  Award
Kowalski i Wspolnicy sp. z o.o.          78     62     71  awarded
Nowak Systemy SA                         65     71     68  -
Testowa Grupa sp. j.                     55     80     66  -
```

## What is actually in the file

| | | |
| --- | --- | --- |
| `state="hidden"` | sheet `Workings` | `Reserve set at 240,000. Kowalski came in 12% under; the others were told nothing.` |
| `<col min="4" max="4" hidden="true">` | column D of `Evaluation` | `Reserve price (EUR)`, `211000`, `238000`, `196000`, `251000` |
| `<row r="4" hidden="true">` | row 4 of `Evaluation` | `Delta Consulting sp. z o.o.`, `82`, `44`, `196000`, `63`, `withdrawn after the deadline - do not list` |
| `xl/comments1.xml` | Halina Probna-Test | `Panel agreed the reserve before the bids were opened. Not for the file we release.` |

The reserve price is what a bidder must not know. The withdrawn bidder is who
the other bidders must not know about. Neither is on the screen and both are
three lines into the XML.

## What it is for

**Two producer facts, both measured against this file rather than read out of
the specification.** They are the reason it exists at all.

`hidden` is written on **every** row, saying `false` on most of them. A reader
that tests whether the attribute is present, rather than what it says, reports
every row in the workbook as concealed. A fixture built from the specification
would carry the attribute only where it mattered and would never have shown
this.

`min` and `max` on a `col` are a **range**, not an identifier. One element can
hide forty columns. Reading only `min` reports the first and loses
thirty-nine.

**A value hidden twice over is reported twice.** `196000` sits in the hidden
row *and* the hidden column, and both findings quote it. They are two answers
to two questions, and `CONTRIBUTING.md` forbids ranking one against the other — the
`filetrail` failure where the stronger claim deleted the more valuable one.

**Nothing visible may be reported as hidden.** `Nowak Systemy SA` is on the
screen. A detector that named it would be calling the visible document a
concealment, which is the same error as reporting a tracked insertion.

## What this specimen does not carry

- **A sheet marked `veryHidden`**, which cannot be brought back through the
  spreadsheet's own interface at all. LibreOffice offers no way to set it, so
  the reader handles it and only a synthetic test exercises it.
- **A filtered row.** ODF distinguishes `table:visibility="filter"` from
  `collapse`; this export flattens the distinction to `hidden="true"` and
  writes no `autoFilter` element at all, so the difference cannot be recovered
  from an .xlsx LibreOffice wrote. See
  [`ods/libreoffice-calc-filtered-rows.ods`](../ods/libreoffice-calc-filtered-rows.md).
- **Excel itself.** Excel is not on this machine. LibreOffice writes valid
  SpreadsheetML, but two producers never agree about everything — the PDF
  specimens proved that twice.
- **Number formatting.** The cells hold bare integers. A formatted cell shows
  `211 000,00 zł` and stores `211000`, so the value quoted here would be the
  stored one rather than the displayed one. Nothing in this file exercises the
  difference.
