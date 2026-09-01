# libreoffice-calc-tracked-changes.xlsx

The same bid comparison as
[`ods/libreoffice-calc-tracked-changes.ods`](../ods/libreoffice-calc-tracked-changes.md),
in the other family. Two edited cells and one deleted row, all three still in
the file.

- 8 061 bytes
- produced by LibreOffice 24.2 Calc

## How it was made

```bash
python3 tests/specimens/sources/build_calc_tracked_changes.py \
    tests/specimens/ods/libreoffice-calc-tracked-changes.ods \
    tests/specimens/xlsx/libreoffice-calc-tracked-changes.xlsx
```

## What is actually in the file

Change tracking in SpreadsheetML is the **shared-workbook revision log**, which
lives in its own folder and is reached by relationship rather than by name:

```text
xl/revisions/revisionHeaders.xml   one <header> per editing session,
                                   carrying userName and dateTime
xl/revisions/revisionLog1.xml      <rcc><oc r="B2" t="n"><v>240000</v>
xl/revisions/revisionLog2.xml      <rcc><oc r="C2" t="inlineStr">…
xl/revisions/revisionLog3.xml      <rrc action="deleteRow" ref="4:4">
```

## What it is for

**Three log parts, and reading the first is not reading the file.** Each header
points at its own log through `xl/revisions/_rels/revisionHeaders.xml.rels`. A
reader that opened `revisionLog1.xml` and stopped would report one change out
of three — and give no sign it had stopped, which is the failure mode this
project cares about most.

That is not hypothetical. The first probe of this file looked only at
`revisionLog1.xml`, concluded the .xlsx export was dropping the other two
changes, and the builder's docstring said so for a while. It was wrong: the
export keeps everything, in parts two and three.
`test_every_log_part_is_read_and_not_only_the_first` asserts the specimen still
has three parts, so the day it stops exercising this the suite says so instead
of quietly passing.

**Who and when are on the header, not on the change.** The author of a cell
change is the `userName` of the session it belongs to. Reading the `rcc` alone
gives a change with nobody attached to it.

**`<nc>` is not to be believed.** LibreOffice writes the "new cell" element
holding the *previous* contents — `240000` in both `oc` and `nc`, and
`rejected on price` in both. A reader that trusted the log would report a cell
that changed from `240000` to `240000`, a finding that contradicts itself on
its own line. The current value is read out of the sheet in both families
instead, which is where a person would look anyway.

**`sId` is a sheet id, not a position and not a name.** `rcc sId="1"` has to be
resolved through the `sheetId` attribute in `xl/workbook.xml`. Using it as an
index reports the change against whichever sheet happens to sit there.

**A string previous value is `t="inlineStr"` with an `<is>`**, where a numeric
one is `t="n"` with a `<v>` — the same two-shapes-per-type problem the ODF file
has, wearing different markup. Either half alone reads half the changes.

## What this specimen does not carry

- **`userNames.xml` with anything in it.** LibreOffice writes it with
  `count="0"` and puts the name on the header instead.
- **An `rfmt`-only revision**, a formatting change with no content, which is
  the spreadsheet's `w:rPrChange`.
- **Excel itself**, whose own change tracking may well write this differently —
  it is a shared-workbook feature Microsoft has been deprecating for years.
