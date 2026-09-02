# libreoffice-calc-rotated-headers.pdf

A bid summary with rotated column headers, one of which is white on the paper.

- 13 801 bytes
- produced by LibreOffice 24.2 Calc, exported to PDF

## How it was made

```bash
python3 tests/specimens/sources/build_rotated_text.py \
    tests/specimens/pdf/libreoffice-calc-rotated-headers.pdf
```

## What a human sees

Two rotated headers reading up the page, `Technical` and `Price`, a `Party`
column and two rows of scores. Between `Price` and the edge of the table there
is a column that appears to be empty.

## What is actually in the file

```text
16 characters painted #ffffff on #ffffff — WITHDRAWN 196000
```

running vertically, in the column that looks empty.

## What it is for

**This file broke the line-grouping rule twice, in two different places.**
Neither break was visible on any horizontal document.

Every detector that reports a line of text groups the page's glyphs into lines
first, because producers disagree wildly about how much text one show-operation
carries. That grouping used to key on **the bottom of the glyph box**. Turn a
line ninety degrees and every glyph in it has a different bottom edge and the
same left edge, so:

```text
low-contrast findings before the fix: 15
  'W'  'I'  'T'  'H'  'D'  'R'  'A'  'W'  'N'  '1'  '9'  '6'  '0'  '0'  '0'
```

It is exactly the failure Chrome's one-glyph-per-`Tj` produced on
`covered_text`, and tesseract's one-operation-per-word produced on
`invisible_text`, arriving a third time from a direction neither of those
predicted.

**The second break was worse, because the first hid it.** Fixing `_lines` did
not fix the report: `low_contrast_text` had never been converted to line
grouping at all. It still worked per show-operation, and nothing had shown
because LibreOffice writes whole words per operation in horizontal text. In
*rotated* cells it writes one glyph at a time. The rule had been broken in
that detector since it was written, and only a rotated page could say so.

**What the grouping keys on now**, and why each part earns its place:

- **The angle**, so a rotated header and a horizontal cell that happen to sit
  at the same height never merge into a line that exists nowhere on the page.
- **The distance across the line**, measured by projecting onto the
  perpendicular of the text direction. For horizontal text this is exactly the
  baseline height it used to be.
- **The glyph's origin rather than its box.** The origin is on the baseline;
  the box's bottom edge is the descent, which a smaller font puts somewhere
  else — so a superscript now stays on the line it belongs to.

Ordering within a line is by distance *along* the direction, so the rotated
line reads `WITHDRAWN 196000` and not whatever order the file emitted it in.

**The two black rotated headers must stay silent.** Rotated column headers are
how a wide table fits on a page; a detector that reported them would be
unusable on any real spreadsheet.

## A false positive this file found, and did not fix

At the default column width the bidder names overflow their cell and
LibreOffice **clips** them. `off-page-text` reports the clipped letter — one
character, in the file, not on the page — which is true and is nothing to do
with concealment.

The specimen was widened rather than the detector tuned. A threshold that
suppressed one-character findings would hide real ones, and the honest problem
is that **no rule here separates a cell boundary from a redaction by clipping**
— which is the same mechanism, used for two different purposes.
It is recorded as open.

## What this specimen does not carry

- **An angle other than 0 or 90.** The grouping is general — it projects onto
  the direction — but only the right angle is exercised by a producer.
- **Text rotated by the page's `/Rotate` entry** rather than by the content
  stream, which is a third way to arrive at the same place.
- **Right-to-left or vertically-set script**, where the advance direction is a
  property of the writing system rather than of a transform.
