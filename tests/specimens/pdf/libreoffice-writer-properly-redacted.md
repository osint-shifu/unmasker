# libreoffice-writer-properly-redacted.pdf

**A control, not a finding.** Same producer, same layout, same four black bars
in the same places — but the text underneath really was removed. The tool must
report nothing here.

- 24 854 bytes, `sha256:b66f1576a657236e…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_libreoffice_writer.py \
    tests/specimens/pdf/libreoffice-writer-properly-redacted.pdf --remove-text
```

The `--remove-text` pass replaces each redacted value with a run of U+00A0 of
the same length before the bars go on, and the bars land on coordinates measured
from the *unredacted* pass. That is what makes this a true pair with
`libreoffice-writer-black-bars.pdf`: the two files differ in whether the text is
still there, and in nothing else — verified, the four bars are byte-for-byte the
same geometry.

> **Corrected 2026-08-31.** This paragraph used to add that the values were set
> in Liberation Mono, so replacing them character-for-character could not shift
> the layout. That was wrong. The `Field` style names Liberation Mono but the
> document declares no font face for it, so LibreOffice substitutes Liberation
> Serif and the values are not monospaced at all — measured through poppler, the
> advance runs from 4.95 to 6.05 points on one line. The claim was never
> load-bearing here, because each value ends its line and the bars come from the
> first pass either way, but it was stated as fact and it was not one.
> `libreoffice-writer-partial-bars.md` records how it came to light.

## What a human sees

Indistinguishable from the failed redaction. Four black bars, two readable
fields.

## What is actually in the file

Nothing under the bars. `pdftotext` gives:

```text
Name:
Email:
Telephone:
Address:
Filed:     17 April 2024
Registry: SYN-2024-0417
```

The labels survive, the values are gone.

## What it is for

The four bars are still present in the content stream, at coordinates identical
to the failed specimen — verified: `x 117.5..268.7 y 684.2..698.5` and the
other three, byte-for-byte the same geometry. So the difference between this
file and the failed one cannot be found by looking at the shapes. It is only
visible by asking what text falls inside them, which is exactly the question the
detector exists to answer.

A detector that fires here is reporting a redaction that worked. That is the
false positive that would cost the tool its credibility fastest, because the
person checking would be looking at a correctly handled document.
