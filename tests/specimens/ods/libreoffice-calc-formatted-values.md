# libreoffice-calc-formatted-values.ods

The same tender timetable as
[`xlsx/libreoffice-calc-formatted-values.xlsx`](../xlsx/libreoffice-calc-formatted-values.md),
in the family that does the work for you.

- 10 040 bytes
- produced by LibreOffice 24.2 Calc, in its own format

## What is actually in the file

```xml
<table:table-cell office:value-type="date" office:date-value="2024-03-15">
  <text:p>2024-03-15</text:p>
</table:table-cell>
<table:table-cell office:value-type="float" office:value="240000">
  <text:p>240 000,00 zl</text:p>
</table:table-cell>
```

The cell carries **both** the stored value and the text the sheet shows, and
this reader takes the text — which is what a person looking at the sheet would
read out to you.

## What it is for

**This is the pair that shows an asymmetry rather than a parity**, and the
distinction matters more than it looks.

Every other paired specimen here exists to prove the two readers agree.
[`libreoffice-calc-hidden-columns`](libreoffice-calc-hidden-columns.md) has a
test asserting both families report exactly the same hiding, because a
disagreement there would mean one reader was wrong.

Here they *do* disagree, and neither is wrong:

| | the .ods reports | the .xlsx reports |
| --- | --- | --- |
| the hidden date | `2024-03-15` | `2024-03-15` |
| the hidden reserve | `240 000,00 zl` | `240000`, with a note naming the format |

The date matches because the OOXML reader renders the serial. The reserve does
not, because the .ods **carries** a displayed value and the .xlsx does not.
Making the .ods quote `240000` to match would throw away evidence one of the
two files actually holds, in exchange for a consistency that describes neither.

The tool reports what each file says. Where a file says more, it says more.

**A note is only printed where one is needed.** The .ods gets none: it had a
displayed value for everything it quoted, so there is nothing to warn a reader
about. Printing the note on every workbook would be a note nobody reads.

## What this specimen does not carry

- **A cell whose displayed text and stored value genuinely conflict**, rather
  than merely differing in formatting — a text cell overwriting a number, for
  instance, which would be a stronger finding than either.
- **A locale whose grouping character is a full stop**, which is the same
  value written a third way.
