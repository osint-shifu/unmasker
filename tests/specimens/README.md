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
| [`docx/libreoffice-writer-tracked-changes.docx`](docx/libreoffice-writer-tracked-changes.md) | LibreOffice 24.2 Writer | a settled figure of 90,000 EUR | the 250,000 EUR it replaced, a deleted sentence, and a candid comment |
| [`docx/libreoffice-writer-metadata-leak.docx`](docx/libreoffice-writer-metadata-leak.md) | LibreOffice 24.2 Writer | one anonymous sentence | two people, a client, a codename and a home directory |
| [`odf/libreoffice-writer-position-note.odt`](odf/libreoffice-writer-position-note.md) | LibreOffice 24.2, in its own format | a two-line note under a header | a struck-out figure, a private comment, an author, a client and a zero-width space |
| [`pdf/libreoffice-writer-metadata-leak.pdf`](pdf/libreoffice-writer-metadata-leak.md) | LibreOffice 24.2 Writer | the same sentence | the same leak, minus what the PDF export drops |
| [`pdf/xmp-survives-the-scrub.pdf`](pdf/xmp-survives-the-scrub.md) | LibreOffice 24.2, then exiftool 12.76 | an Info dictionary that looks cleaned | an XMP packet that still holds all of it |
| [`pdf/chrome-transparent-text.pdf`](pdf/chrome-transparent-text.md) | Skia/PDF m152 (headless Chrome) | two paragraphs and a blank gap | two more paragraphs, painted at no opacity |
| [`pdf/redacted-scan-with-ocr.pdf`](pdf/redacted-scan-with-ocr.md) | LibreOffice, Ghostscript, tesseract 5.3.4, ImageMagick, pypdf | a scan with the figure blacked out | an OCR layer made before the redaction, still spelling it |
| [`pdf/libreoffice-writer-image-over-text.pdf`](pdf/libreoffice-writer-image-over-text.md) | LibreOffice 24.2, ImageMagick | a black bar over a name | the name, under a *picture* and not a shape |
| [`pdf/coverage-edge.pdf`](pdf/coverage-edge.md) | LibreOffice 24.2 | four marks, covered by 100%, 75%, 50% and 25% | where this tool's threshold actually is |
| [`pdf/text-on-an-image.pdf`](pdf/text-on-an-image.md) | LibreOffice 24.2, ImageMagick | white text on a picture | nothing — and a note saying it could not be judged |
| [`pdf/libreoffice-writer-pdf-comments.pdf`](pdf/libreoffice-writer-pdf-comments.md) | LibreOffice 24.2 | a two-line board minute | two comments attached to the page and not part of it |

The first two are failed redactions. The next two must not be reported, and for
different reasons: one was redacted correctly, the other has nothing to search.
The partial-bars file holds the detector honest about *how much* a bar covers.
The hidden-in-plain-sight file has nothing drawn over anything — everything it
hides, it hides by colour or by position — so every bar detector must stay
silent on it. The first DOCX is the tier-2 specimen, and every tier-2
detector fires on it exactly once. The second hides nothing by drawing or by
character: its deletions are text the application has agreed not to display.
The last pair is one source document in two containers, because the two carry
different amounts of the same metadata and a tool tried on one of them would
have a partial idea of what metadata is.

## Rebuilding them

`sources/` holds the builders. They need `soffice`, `google-chrome`, `gs`,
`pdftotext` and `exiftool` on `PATH`, and they write each file through those
tools rather than emitting its bytes directly — which is the point. Where a
measurement is needed, it comes from poppler rather than from this project's
own code, for the same reason. See each specimen's `.md` for the exact
command.

The committed PDFs are the artefacts under test. Rebuilding produces a file that
differs in its `/CreationDate` and in font subset naming, so a rebuild is not
byte-identical and is not expected to be. Rebuild to add a specimen or to check
a builder still runs, not as part of the test suite.

## What is still missing

Named here so their absence is not mistaken for coverage:

- **A bar covering a glyph vertically** rather than horizontally — a rule drawn
  along a line clips its descenders, which is the same fraction arrived at a
  different way. `coverage-edge.pdf` closed the horizontal case and records
  where the threshold is; the threshold is on area and does not care which way
  the overlap runs, but no file demonstrates that.
- **Text outside the MediaBox.** LibreOffice refuses to emit it, so the
  off-page case is represented only by a CropBox smaller than the MediaBox.
  Another producer is needed for the other half.
- **A tiling pattern behind text.** `text-on-an-image.pdf` covers the picture
  case; a pattern fill is the other way a background becomes unreadable.
- **An XMP packet written in attribute form**, which is how Adobe writes them.
  Handled, and only a synthetic test exercises it: exiftool writes element form
  and offers no way to ask for the other.
- **A true PDF shading.** Both LibreOffice and Chrome flatten a gradient before
  it reaches the file — LibreOffice into dozens of solid strips, Chrome into a
  single fill — so no producer here emits `sh` at all.
- **XMP outside a PDF.** DOCX, JPEG and TIFF carry packets too.
- **Rotated or vertically-set text.** Lines are grouped by the bottom of the
  glyph box, which is exact for horizontal text and wrong for anything else.
- **Producers not on this machine.** Acrobat and Word draw their own way, and
  LibreOffice and Chrome already disagree with each other.
- **An annotation carrying an appearance stream.** Comments now have a
  specimen, but `/AP` is where a bar drawn as an annotation would live, and no
  producer here writes one — LibreOffice draws its shapes into the content
  stream, and a `/Square` written by hand renders in nothing without an `/AP`,
  which is precisely why the appearance stream is the part that matters. The
  tool notes such an annotation rather than passing over it.
- **Redaction by clipping path.** Handled by `off-page-text` and covered only
  by a unit test; no producer here emits it.
- **A raster page with an invisible OCR text layer underneath**, which is a
  failed redaction that `flattened-to-image.pdf` does not represent.
- **Word's own OOXML.** Word is not on this machine, so every DOCX here was
  written by LibreOffice. It emits valid revision markup, but two producers
  never agree about everything — the PDF specimens proved that twice.
- **Spreadsheets and presentations**, in either family. `.xlsx`, `.pptx`,
  `.ods` and `.odp` are the same containers with different body parts, and
  nothing here reads or tests one.
- **`w:moveFrom` / `w:moveTo` from a real producer.** LibreOffice does not emit
  move tracking; the reader handles it and only a synthetic test exercises it.
- **Nothing, on this front.** Every detector now fires on a committed file that
  a producer wrote, and `test_every_detector_now_has_a_specimen` holds that
  position. It was the gap that mattered most: a detector covered only by
  hand-built pages is exactly the shape of the bug that started this project.
