# libreoffice-writer-black-bars.pdf

A failed redaction. Four black bars, four values still in the text layer.
**This is the primary specimen**: the one the rectangle-over-text detector has
to work on.

- 25 544 bytes, `sha256:fbaeef0d794f2bdb…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

`sources/build_libreoffice_writer.py`, on this machine, 2026-08-31:

```bash
python3 tests/specimens/sources/build_libreoffice_writer.py \
    tests/specimens/pdf/libreoffice-writer-black-bars.pdf
```

The script writes a Flat ODF document and hands it to `soffice --convert-to
pdf`. **LibreOffice writes the PDF**; nothing in this repository emits a path
or a fill operator by hand. The bars are `<draw:custom-shape>` rectangles with
`style:run-through="foreground"`, which is what puts them in front of the text
rather than behind it — the real-world failure exactly.

It runs in two passes. The first exports the text alone and measures where each
line actually landed, using pypdf's `visitor_text`; the second re-exports with
the bars placed on those measured positions. Guessed coordinates would have
produced bars that *almost* cover their text, and a detector tuned against that
is worse than none.

## What a human sees

Six labelled fields. `Name`, `Email`, `Telephone` and `Address` have their
values covered by solid black bars; the labels stay legible. `Filed` and
`Registry` are untouched and readable.

## What is actually in the file

All four covered values, in the text layer, readable by any parser:

| field | value under the bar |
| --- | --- |
| Name | `Wanda Testowa-Przyklad` |
| Email | `w.testowa@example.org` |
| Telephone | `+48 601 000 000` |
| Address | `ul. Przykladowa 12/3, 00-001 Warszawa` |

`pdftotext` reads every one of them — confirmed with a tool that is not pypdf,
so the finding does not depend on the library the tool itself uses.

## What this specimen proved, and it was not what we expected

**LibreOffice does not draw a rectangle with the `re` operator.** Each bar is a
closed polygon filled with even-odd:

```text
0 0 0 rg
193.1 684.239 m  117.5 684.239 l  117.5 698.489 l
268.7 698.489 l  268.7 684.239 l  193.1 684.239 l  h  f*
```

Six points, `h`, `f*`. Axis-aligned, but expressed as a path, and it starts at
a point partway along the bottom edge rather than at a corner.

There is exactly one `re` in the whole page, and it is not a bar:

```text
0 0.028 595.275 841.861 re
W* n
```

That is the page-sized clipping rectangle. `W* n` sets a clip and discards the
path without painting it.

This matters more than it looks. `HANDOFF.md` recorded `re ×1` in a sibling
LibreOffice PDF as evidence that the operators were present — but that single
`re` was the page clip in that file too. A detector that looks for `re` followed
by `f` finds **zero** bars here, and a hand-built fixture written from the PDF
specification would have hidden that behind a green test suite. This is the
`filetrail` HEIC bug in a new costume, caught before the detector was written,
which is the whole reason the specimen comes first.

## Coordinate system

The identity matrix. No `cm` anywhere on the page, so operand values are page
coordinates directly. Contrast `chrome-print-css-overlay.pdf`, where they are
not.
