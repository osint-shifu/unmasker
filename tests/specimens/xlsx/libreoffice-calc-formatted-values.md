# libreoffice-calc-formatted-values.xlsx

A tender timetable whose hidden row carries a date and a currency figure.
Neither is stored as the sheet shows it.

- 5 610 bytes
- produced by LibreOffice 24.2 Calc

Its sibling [`ods/libreoffice-calc-formatted-values.ods`](../ods/libreoffice-calc-formatted-values.md)
is the same source document in the other family, which stores the same two
values completely differently.

## How it was made

```bash
python3 tests/specimens/sources/build_calc_formatted_values.py \
    tests/specimens/xlsx/libreoffice-calc-formatted-values.xlsx \
    tests/specimens/ods/libreoffice-calc-formatted-values.ods
```

## What a human sees

```text
Stage         Date         Reserve
Bids opened   2024-04-02   -
```

Row 3 is hidden. On the screen it would read
`Decision taken | 2024-03-15 | 240 000,00 zl`.

## What is actually in the file

```xml
<c r="B3" s="1" t="n"><v>45366</v></c>
<c r="C3" s="2" t="n"><v>240000</v></c>
```

and, two indirections away in `xl/styles.xml`:

```xml
<cellXfs><xf numFmtId="164"…/><xf numFmtId="165"…/><xf numFmtId="166"…/></cellXfs>
<numFmt numFmtId="165" formatCode="yyyy\-mm\-dd"/>
<numFmt numFmtId="166" formatCode="#,###.00&quot; zl&quot;"/>
```

## What it is for

**Without resolving the format, this file reports its hidden row as
`Decision taken | 45366 | 240000`.** That is the file's arithmetic, not the
document's content, and it is worse than useless in a report: a reader cannot
match it against the sheet, and `45366` gives no clue that it is a date at all.

**The line between rendering and quoting is drawn where exactness ends.**

*A date is rendered.* A date cell holds a count of days and nothing else, so
the conversion is exact — serial days from 1899-12-30, which is what both
producers count from. There is no rounding, no locale and nothing to get
subtly wrong.

*Everything else is quoted as stored, and the format is named in a note.*
Rendering `#,###.00" zl"` means writing a number formatter: grouping,
decimals, negatives in brackets, conditional sections, colours. One that is
nearly right quotes a figure that is nearly right, and in a forensic report a
figure that is nearly right is worse than an exact quotation of what the file
holds with a sentence saying what the sheet does to it.

**Three ways to read the format wrongly, each with a test:**

- `s="2"` indexes **`cellXfs`**, and `xl/styles.xml` also has a `cellStyleXfs`
  block full of elements that look identical. Sweeping up every `xf` reads the
  wrong format for every cell.
- A format code's literal text is not tokens. `#,###.00" zl"` has no date in
  it, but `0.00"m"` has an `m` inside a literal, and this file's own
  `yyyy\-mm\-dd` has escaped hyphens. Testing the raw string reports a
  currency suffix as a date.
- A workbook may count its days from 1904 (`date1904="true"` in
  `workbookPr`). This one does not; a reader that ignored the attribute would
  report every date in one that does four years and a day early.

## What this specimen does not carry

- **A 1904-epoch workbook.** LibreOffice writes `date1904="false"` and offers
  no way to ask for the other from the command line, so the branch is covered
  only by a synthetic test.
- **A time of day.** The renderer adds `HH:MM` when the format has time tokens
  and the serial has a fraction; no cell here exercises it against a producer.
- **A conditional or coloured format** (`[Red]-0.00;[Blue]0.00`), which is the
  case that makes writing a real formatter expensive.
- **Excel**, which may well number its built-in formats the same way and write
  its custom ones differently.
