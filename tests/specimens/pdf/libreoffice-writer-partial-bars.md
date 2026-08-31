# libreoffice-writer-partial-bars.pdf

The bars are dragged too short. Each stops in the gap before its value's last
word, and that word stays legible on the page.

This is the specimen the `tests/specimens/README.md` gap list asked for, and it
is the one that makes the difference between reporting *that* a bar covers text
and reporting *which* text it covers. Without it, a detector that reported the
whole line whenever any part of it was touched would pass every other test in
this directory.

- 25 539 bytes, `sha256:6186bd7a16878bd7…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_libreoffice_writer.py \
    tests/specimens/pdf/libreoffice-writer-partial-bars.pdf --partial
```

Same two-pass builder as the full-coverage specimen, with one difference that
matters more than its size: **the bars are placed on poppler's measurements,
not on this project's.**

`pdftotext -bbox` reports every word's box on the page. A fixture measured with
the tool under test would prove only that the tool agrees with itself, which was
never in doubt; poppler is a wholly separate implementation, so a bar placed on
its numbers is an independent statement about where the text is. The two agree:
poppler puts the email word's top at 163.0998pt and the full-coverage
specimen's email bar sits at 163.3pt.

Each bar ends **midway through a gap between two words**, so no word straddles
an edge. That is what lets the expected answer be stated without per-character
geometry: which words are covered follows from poppler's boxes alone.

## What a human sees

```text
Name:       ████ Testowa-Przyklad
Email:      █████████████████████
Telephone:  ███████████ 000
Address:    ████████████████████████████ Warszawa
```

Three of the four values keep their last word in plain sight. This is what a
box dragged too short looks like, and it is a more common failure than a box
that misses entirely — the person doing it can see the bar and stops looking.

## What is actually in the file

| field | covered | still legible on the page |
| --- | --- | --- |
| Name | `Wanda` | `Testowa-Przyklad` |
| Email | `w.testowa@example.org` | *(nothing)* |
| Telephone | `+48 601 000` | `000` |
| Address | `ul. Przykladowa 12/3, 00-001` | `Warszawa` |

The e-mail address is one word with no gap to stop in, so its bar covers the
whole value. That row is the full-coverage case and is here for contrast.

## What it is for

A detector must report the covered column and nothing more. Reporting
`Wanda Testowa-Przyklad` here would be an overstatement in the safest-feeling
direction, and the first reader who looked at the page would see the tool
exaggerating — which costs more than the finding was worth.

## A correction this specimen forced

Building it revealed that the `Field` paragraph style names Liberation Mono but
the document declares no font face for it, so LibreOffice substitutes
Liberation Serif and **the values are not monospaced**. Measured through
poppler the real advance runs from 4.95 to 6.05 points across the same line.

The full-coverage specimen is unaffected — its bars are padded generously
enough that the estimate error never showed — but that is exactly the kind of
error a fixture can hide, which is why this specimen does not rely on the
estimate at all.
