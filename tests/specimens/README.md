# Specimens

Specimens live here and **are committed**, unlike the sibling project's corpus.
They are the test suite: a detector written against a hand-built fixture proves
nothing about a document a real producer wrote.

Each specimen records, in a sibling `.md` file, which tool produced it and how,
what a human sees when it is opened, and what is actually in the file
underneath.

Only synthetic or clearly licensed material. Nothing from a real case. Every
particular in these documents is invented; the e-mail domain is `example.org`,
which RFC 2606 reserves for the purpose.

## What is here

| specimen | producer | a human sees | a machine reads |
| --- | --- | --- | --- |
| [`pdf/libreoffice-writer-black-bars.pdf`](pdf/libreoffice-writer-black-bars.md) | LibreOffice 24.2 Writer | four black bars | the four values, intact |
| [`pdf/chrome-print-css-overlay.pdf`](pdf/chrome-print-css-overlay.md) | Skia/PDF m152 (headless Chrome) | four black bars | the four values, intact |
| [`pdf/libreoffice-writer-properly-redacted.pdf`](pdf/libreoffice-writer-properly-redacted.md) | LibreOffice 24.2 Writer | four black bars | nothing — control |
| [`pdf/flattened-to-image.pdf`](pdf/flattened-to-image.md) | Ghostscript `pdfimage24` | four black bars | no text layer at all — control |

The first two are failed redactions and must be found. The last two must not be
reported as findings, and for different reasons: one was redacted correctly,
the other has nothing to search.

## Rebuilding them

`sources/` holds the builders. They need `soffice`, `google-chrome` and `gs` on
`PATH`, and they write the PDF through those tools rather than emitting PDF
operators directly — which is the point. See each specimen's `.md` for the exact
command.

The committed PDFs are the artefacts under test. Rebuilding produces a file that
differs in its `/CreationDate` and in font subset naming, so a rebuild is not
byte-identical and is not expected to be. Rebuild to add a specimen or to check
a builder still runs, not as part of the test suite.

## What is still missing

Named here so their absence is not mistaken for coverage:

- **A bar that only partly covers its text.** Every bar here covers its value
  completely. The geometry edge — what counts as covered — is untested.
- **Producers not on this machine.** Acrobat and Word draw their own way, and
  LibreOffice and Chrome already disagree with each other.
- **Redaction by image, annotation or clipping path**, rather than a filled
  shape.
- **A raster page with an invisible OCR text layer underneath**, which is a
  failed redaction that `flattened-to-image.pdf` does not represent.
- **Everything outside tier 1.** No specimen yet for invisible render mode
  (`3 Tr`), text in the colour of its background, text off the page, zero-width
  or bidi characters, or DOCX tracked changes.
