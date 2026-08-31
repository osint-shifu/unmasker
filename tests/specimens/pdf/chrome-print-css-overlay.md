# chrome-print-css-overlay.pdf

The same failed redaction, from a second producer with a different rendering
engine. It exists because one producer is an anecdote: if two independent
engines disagree about how to emit a filled black box, the detector has to
handle both, and it is far cheaper to learn that now than after the interpreter
is written.

They do disagree. See below.

- 32 102 bytes, `sha256:3dc6583d205bc641…`
- `/Producer` `Skia/PDF m152`, `/Creator` `HeadlessChrome/152.0.0.0`

## How it was made

`sources/build_chrome_print.py`, on this machine, 2026-08-31:

```bash
python3 tests/specimens/sources/build_chrome_print.py \
    tests/specimens/pdf/chrome-print-css-overlay.pdf
```

The script writes an HTML page and prints it with `google-chrome --headless
--print-to-pdf`. The redaction is a CSS overlay: each hidden value sits in a
`position: relative` span with an absolutely positioned black child stretched
over it. That is how a web page hides something, and printing such a page is a
real route to a released PDF. The text is painted first and the box on top of
it; nothing is removed.

The content is identical to `libreoffice-writer-black-bars.pdf`, so the two
files differ only in who produced them.

## What a human sees

The same six labelled fields, the same four values covered by solid black bars,
the same two left readable.

## What is actually in the file

The same four values, in the text layer, read out by `pdftotext`.

## What this specimen proved

**Chrome draws the bars with `re` and `f`** — the idiom LibreOffice does not
use:

```text
112 135 199 18 re f
112 168 190 18 re f
112 202 138 18 re f
112 235 331 18 re f
```

Two producers, two entirely different content-stream idioms for the same
picture. The interpreter has to handle filled paths generally, not one
operator.

Two further traps, both of which would silently produce wrong answers rather
than obvious ones:

**The operands are not page coordinates.** Chrome nests two transforms, and the
first one flips the Y axis:

```text
.23999999 0 0 -.23999999 0 841.91998 cm
q
  293.75 293.75 1889.7949 2917.334 re
  W* n
  q
    3.125 0 0 3.125 293.75 293.75 cm
```

Net scale 0.24 × 3.125 = 0.75, which is 96 dpi CSS pixels into points, with a
negative determinant. The text matrices carry a matching `1 0 0 -1 … Tm` to
turn the glyphs back the right way up. `112 135 199 18 re` becomes
x 154.5–303.7, y 656.7–670.2 in page space. Ignore the CTM and every bar lands
somewhere plausible but wrong — on the page, just not where it is.

**The fill colour is set once and inherited.** There is exactly one `rg` in the
whole stream. Black text and black bars share it, and no `rg` immediately
precedes any of the four fills. A detector that pattern-matches "`rg` then
`re` then `f`" finds nothing, and one that treats "black fill" as the signal
cannot tell a bar from the body text. The graphics state has to be tracked
through `q`/`Q`, not matched.

## Coordinate system

Nested, and Y-flipped. This is the specimen that forces the interpreter to
compose the CTM properly.
