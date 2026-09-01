# libreoffice-calc-clipped-overflow.pdf

A case queue whose first column is too narrow, so LibreOffice clips what does
not fit. Nothing here is hidden on purpose.

- 11 920 bytes
- produced by LibreOffice 24.2 Calc, exported to PDF

## How it was made

```bash
python3 tests/specimens/sources/build_clipped_overflow.py \
    tests/specimens/pdf/libreoffice-calc-clipped-overflow.pdf
```

## What a human sees

```text
Case                            Owner
KZ-2024-0031 opene              Probna
KZ-2024-0044 withdrawn befor    Przyklad
```

The case descriptions run out of room and stop mid-word.

## What is actually in the file

The whole of each description, with a clipping path that cuts it at the column
boundary. One character of each falls entirely outside the clip:

```text
'e'   at x 146.6-152.2, visible area ends at x 141.7
'd'   at x 142.2-147.7, same
```

## What it is for

**This is a control against the tool's own noise**, and it is the first
specimen here whose purpose is to make a finding *weaker* rather than to make
one appear.

A cell boundary and a redaction by clipping are the **same mechanism**: text is
drawn, a clipping path is in force, part of the text falls outside it. One is a
column too narrow for what was typed into it; the other is a hidden sentence.
Nothing in the file distinguishes them.

Before this file, `off-page-text` reported both in the same words and with the
same evidence class. A spreadsheet exported to PDF can produce a screenful of
the first — and a reader who has learned to scroll past them will scroll past
the second.

**What can be said is what the rest of the line supports.** Every clipped run
here has visible text beside it on the same line, which is what an overflow
looks like and is not what a wholly concealed line looks like. So the finding
is `circumstantial` and its summary says so, quoting the visible remainder:

```text
● 1 character at x 146.6-152.2, y 739.4-750.5, entirely outside the
  visible area x 56.7-141.7, y 725.6-764.0; the rest of the line is on
  the page, so this may be text overflowing its box - 'KZ-2024-0031
  openProbna'
```

**It is not suppressed, and that is the whole point of using the evidence class
instead of a filter.** A redaction that clips only the second half of a line
looks exactly like an overflow. A tool that deleted the finding would have
decided for its reader, which is the one thing `CLAUDE.md` says it must never
do. Making the claim weaker and saying why leaves the judgement where it
belongs.

The control for the other half is
[`libreoffice-writer-hidden-in-plain-sight.pdf`](libreoffice-writer-hidden-in-plain-sight.md),
whose off-page line has no visible remainder anywhere and stays `direct`.

**It also fixed the line grouping in a fourth place.** `off_page_text` was
still working per show-operation, like `low_contrast_text` before it — so
"the rest of the line" could not even have been asked before the detector was
moved onto `_lines`.

## What this specimen does not carry

- **A redaction that clips the second half of a line**, which would be the
  hard case: identical evidence, opposite meaning. No producer here writes
  one, and the tool would report it exactly as it reports this file — which is
  correct, and is why the finding survives rather than being filtered.
- **A clip that is not a rectangle.** A clipping path can be any shape; every
  clip here is a cell.
- **Text clipped by a form XObject's `/BBox`** rather than by a `W n` path.
