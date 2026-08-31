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
the same length before the bars go on. The values are set in Liberation Mono,
where every glyph including the space has the same advance, so the layout does
not shift by a hair. The bars land on coordinates measured from the *unredacted*
pass, which is what makes this a true pair with
`libreoffice-writer-black-bars.pdf`: the two files differ in whether the text is
still there, and in nothing else.

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
