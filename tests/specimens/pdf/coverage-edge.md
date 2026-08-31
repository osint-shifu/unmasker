# coverage-edge.pdf

Four single-character marks on a line, under four bars covering 100%, 75%, 50%
and 25% of them. This file records where the tool's threshold actually is.

- 19 600 bytes, `sha256:d64dc3c25d0508f2…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_coverage_edge.py \
    tests/specimens/pdf/coverage-edge.pdf
```

Two passes. The first exports the marks alone so `pdftotext -bbox` can measure
each one; the second draws a bar over the stated fraction of each box.

The marks are single characters and space-separated **on purpose**: poppler
reports a box for each word, so a one-character word's box *is* a glyph's box.
That is what makes a fraction of a glyph measurable without asking this
project's own code where the glyph is — the same rule every other specimen's
geometry follows.

## What a human sees

```text
Marks: █ ▐ ▌ ▎
```

`A` gone entirely. `B` with a sliver showing. `C` half a letter. `D` mostly
legible.

## What the tool reports

| mark | bar covers | reported |
| --- | --- | --- |
| A | 100% | yes |
| B | 75% | yes |
| C | 50% | no |
| D | 25% | no |

The threshold is 55% of a glyph's area — `COVERAGE` in
`src/unmasker/pdf/detectors.py`.

## Why a file rather than a constant

Every other bar in every other specimen stops in the gap between two words, so
no glyph is ever half covered and the question never comes up. That is
convenient and it is not the world: a bar dragged by hand lands wherever the
hand stopped.

A threshold has to be somewhere, and wherever it is, a document exists that
sits just the wrong side of it. What can be done about that is to write the
position down in a file that fails when it moves, so that changing it is a
decision somebody makes rather than a number that drifts while nobody is
looking.

## What it is not

It is not a claim that 55% is the right number. It is a record of what the
number is. If a real document ever argues for a different one, this specimen is
what makes the change visible — and the argument, not this file, is what should
settle it.

## What is still untested at the edge

A bar covering a glyph **vertically** rather than horizontally: a rule drawn
along a line of text clips its descenders, and the same fraction arrived at a
different way. The threshold is on area and does not care which way the overlap
runs, but no file demonstrates that.
