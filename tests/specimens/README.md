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
| [`pdf/libreoffice-writer-partial-bars.pdf`](pdf/libreoffice-writer-partial-bars.md) | LibreOffice 24.2 Writer | four bars dragged too short | the covered words, and only those |
| [`pdf/libreoffice-writer-hidden-in-plain-sight.pdf`](pdf/libreoffice-writer-hidden-in-plain-sight.md) | LibreOffice 24.2 Writer, cropped with pypdf | one readable line and a navy bar | three lines hidden by colour and by position |
| [`docx/libreoffice-writer-hidden-characters.docx`](docx/libreoffice-writer-hidden-characters.md) | LibreOffice 24.2 Writer | four ordinary lines | a zero-width space, an override, a hidden instruction, a homoglyph |

The first two are failed redactions. The next two must not be reported, and for
different reasons: one was redacted correctly, the other has nothing to search.
The partial-bars file holds the detector honest about *how much* a bar covers.
The hidden-in-plain-sight file has nothing drawn over anything — everything it
hides, it hides by colour or by position — so every bar detector must stay
silent on it. The DOCX is the tier-2 specimen, and every tier-2 detector fires
on it exactly once.

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

- **A bar drawn across the middle of a word**, so that one glyph is half
  covered. `libreoffice-writer-partial-bars.pdf` closed the partial-coverage
  gap, but every bar in it stops in a gap between words; the genuinely
  ambiguous edge is still untested.
- **Text outside the MediaBox.** LibreOffice refuses to emit it, so the
  off-page case is represented only by a CropBox smaller than the MediaBox.
  Another producer is needed for the other half.
- **Text hidden behind a shading or a pattern.** `low-contrast-text` reports
  nothing when it cannot read the background colour, which is the honest answer
  and also an untested one.
- **Rotated or vertically-set text.** Lines are grouped by the bottom of the
  glyph box, which is exact for horizontal text and wrong for anything else.
- **Producers not on this machine.** Acrobat and Word draw their own way, and
  LibreOffice and Chrome already disagree with each other.
- **Redaction by image, annotation or clipping path**, rather than a filled
  shape.
- **A raster page with an invisible OCR text layer underneath**, which is a
  failed redaction that `flattened-to-image.pdf` does not represent.
- **DOCX tracked changes.** `w:del` keeps deleted text in the file, and no
  specimen carries any. Word is not on this machine, so LibreOffice will have to
  produce them, and LibreOffice and Chrome already disagree with each other about
  PDF — expect the same for OOXML.
- **The rest of tier 1 and tier 3.** No specimen yet for invisible render mode
  (`3 Tr`), text in the colour of its background, or text off the page.
