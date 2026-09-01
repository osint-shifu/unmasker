# libreoffice-calc-tracked-changes.ods

A bid comparison with change tracking left on. Two cells were edited and one
row deleted, and every earlier value is still in the file.

- 11 175 bytes
- produced by LibreOffice 24.2 Calc, in its own format

Its sibling [`xlsx/libreoffice-calc-tracked-changes.xlsx`](../xlsx/libreoffice-calc-tracked-changes.md)
is the same source document in the other family, which keeps the same three
changes somewhere else entirely.

## How it was made

```bash
python3 tests/specimens/sources/build_calc_tracked_changes.py \
    tests/specimens/ods/libreoffice-calc-tracked-changes.ods \
    tests/specimens/xlsx/libreoffice-calc-tracked-changes.xlsx
```

## What a human sees

```text
Party                            Offer    Note
Kowalski i Wspolnicy sp. z o.o.  198000   shortlisted
Nowak Systemy SA                 231000   held
```

## What is actually in the file

| | | |
| --- | --- | --- |
| `table:cell-content-change` | Halina Probna-Test, 2024-06-12T09:14 | cell B2 was `240000` |
| `table:cell-content-change` | Piotr Przyklad, 2024-06-12T16:40 | cell C2 was `rejected on price` |
| `table:deletion` | Halina Probna-Test, 2024-06-13T08:02 | row 3, and **no content at all** |

The offer was edited down by a fifth after someone had already written it off
on price, and the sheet shows one number and one word.

## What it is for

**This is the only finding in the project where both columns carry real text.**
Everywhere else — a black bar, a zero-width character, a tracked deletion — the
`human sees` column is an absence, because the hidden thing has nothing on the
page to sit beside. A changed cell does: the reader is looking at `198000`
while the file also holds `240000`, and the report puts them on two lines under
each other.

```text
  ● cell B2 of sheet "Bids" was changed by Halina Probna-Test on
    2024-06-12T09:14:00; the earlier value is still in the file
  │ human sees     198000
  │ machine reads  240000
```

**The previous value is written two different ways, and which one depends on
its type.** This is the producer fact the specimen exists for, and it is
invisible in a fixture built from the specification, which describes both forms
and says nothing about when each appears:

```xml
a number  <table:change-track-table-cell office:value-type="float"
                                         office:value="240000"/>
a string  <table:change-track-table-cell office:value-type="string">
            <text:p>rejected on price</text:p>
          </table:change-track-table-cell>
```

The builder writes **both** the attribute and the paragraph for both cells.
LibreOffice keeps whichever suits the type and silently drops the other, so a
reader that knows one form reads half the changes — and then reports the file
as though that were all of them, which is worse than reading none.

**A cell address has to be turned into one a person can act on.** ODF counts
`table:row` and `table:column` from zero, so the change on `B2` is written as
row 1, column 1. Passing that through would send a reader to `A1`.

**A tracked deletion carries no content.** LibreOffice writes the author, the
date and the position of the deleted row, and no cells. So it quotes nothing,
and a finding that quotes nothing teaches a reader to skip findings: it is
remarked on, and counted into the revision history, which is what
`w:rPrChange` established in the DOCX reader.

**The editors are still one fact about the file.** Two cell changes and a
deletion by two people produce one `revision-history` finding, not three. The
same rule the DOCX reader follows, in a different container.

## What this specimen does not carry

- **An insertion.** ODF tracks those too, and text that was *added* is on the
  sheet in plain sight — the same reason a `w:ins` is not reported as hidden.
- **A deletion that kept its cells.** The format allows `<table:deletions>` to
  hold the removed content; LibreOffice writes none, so the reader's handling
  of a deletion that quotes something is untested against a producer.
- **A change to a cell on a hidden sheet**, which would be concealed twice
  over by two different mechanisms.
- **Excel.** Not on this machine. Its change tracking is a shared-workbook
  feature it has been deprecating for years, and it may well disagree.
