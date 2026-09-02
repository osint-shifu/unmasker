# libreoffice-calc-filtered-rows.ods

An internal case queue with two rows a filter is holding back rather than a
person having hidden them.

- 11 208 bytes
- produced by LibreOffice 24.2 Calc, in its own format

## How it was made

```bash
python3 tests/specimens/sources/build_calc_filtered_rows.py \
    tests/specimens/ods/libreoffice-calc-filtered-rows.ods
```

## What a human sees

```text
Case           Status  Party
KZ-2024-0031   open    Meridian Trust BV
KZ-2024-0044   open    Testowa Grupa sp. j.
```

## What is actually in the file

| | | |
| --- | --- | --- |
| `table:visibility="filter"` | rows 3 and 4 | `KZ-2023-0912`, `referred to prosecutor`, `Nowak Systemy SA` |
| `table:visibility="filter"` | | `KZ-2023-0948`, `referred to prosecutor`, `Kowalski i Wspolnicy sp. z o.o.` |

## What it is for

**`table:visibility` has three values and only two of them mean the same
thing.** `collapse` is a person having hidden the row. `filter` is a filter
holding it back: the rows come back the moment it is cleared, and whoever is
looking at the screen set it and knows they set it. Both put text in the file
that is not on the screen, so both are reported — and they are not the same
claim, so they are not reported the same way. The filtered rows are
`circumstantial`: consistent with concealment, and consistent with an ordinary
afternoon's work. `CONTRIBUTING.md` asks for a word a reader can argue with, and this
is the case that word exists for.

**The two rows are consecutive**, so the run-collapsing rule has a run to
collapse. One finding covers rows 3 to 4, because hiding a block is one act by
one person and a finding per row is a report nobody finishes reading.

**A filtered row must not also be counted as a hidden one.** Two names for one
row is the report telling a reader there is more here than there is.

## Why this is a separate file, and not another row in the other specimen

Exporting this to .xlsx **loses the distinction entirely.** LibreOffice writes
`hidden="true"` on the row and no `autoFilter` element at all, so nothing in
the resulting workbook says a filter was ever involved. That is a true fact
about the two formats and it is stated here rather than hidden: the same source
document reports `filtered-rows` as an .ods and `hidden-rows` as an .xlsx,
because that is what each file says.

Folding this into `libreoffice-calc-hidden-columns` would have cost that
specimen its strongest test — that both families report the same hiding — in
exchange for an asymmetry better documented on its own.

## What this specimen does not carry

- **An `autoFilter` element.** Excel writes one and records the filter's
  criteria in it; LibreOffice's ODS does not, so nothing here says *what* the
  filter was set to.
- **A filtered column.** ODF allows `table:visibility="filter"` on a column,
  and no producer here emits one; the reader treats it as a hidden column,
  which is untested against a real file.
