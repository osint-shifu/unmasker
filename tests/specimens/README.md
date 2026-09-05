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
| [`xlsx/libreoffice-calc-hidden-columns.xlsx`](xlsx/libreoffice-calc-hidden-columns.md) | LibreOffice 24.2 Calc | a tender evaluation, columns A B C E F | a hidden column, a hidden row, a hidden sheet and a candid comment |
| [`ods/libreoffice-calc-hidden-columns.ods`](ods/libreoffice-calc-hidden-columns.md) | LibreOffice 24.2 Calc | the same evaluation | the same four, stated the other family's way |
| [`ods/libreoffice-calc-filtered-rows.ods`](ods/libreoffice-calc-filtered-rows.md) | LibreOffice 24.2 Calc | two open cases | two more the filter is holding back |
| [`ods/libreoffice-calc-tracked-changes.ods`](ods/libreoffice-calc-tracked-changes.md) | LibreOffice 24.2 Calc | a bid of 198 000 | the 240 000 it replaced, and who edited it |
| [`xlsx/libreoffice-calc-tracked-changes.xlsx`](xlsx/libreoffice-calc-tracked-changes.md) | LibreOffice 24.2 Calc | the same bid | the same three changes, in a revision log of three parts |
| [`xlsx/libreoffice-calc-formatted-values.xlsx`](xlsx/libreoffice-calc-formatted-values.md) | LibreOffice 24.2 Calc | a timetable with a row missing | a hidden date stored as `45366` and a reserve stored as `240000` |
| [`ods/libreoffice-calc-formatted-values.ods`](ods/libreoffice-calc-formatted-values.md) | LibreOffice 24.2 Calc | the same timetable | the same row, with the displayed text kept in the cell |
| [`pdf/libreoffice-calc-rotated-headers.pdf`](pdf/libreoffice-calc-rotated-headers.md) | LibreOffice 24.2 Calc | two rotated headers and a column that looks empty | a third header, sideways, white on the paper |
| [`pdf/libreoffice-calc-clipped-overflow.pdf`](pdf/libreoffice-calc-clipped-overflow.md) | LibreOffice 24.2 Calc | two case notes that stop mid-word | the rest of each, clipped by a column boundary — and **nothing hidden** |
| [`pptx/libreoffice-impress-hidden-slide.pptx`](pptx/libreoffice-impress-hidden-slide.md) | LibreOffice 24.2 Impress | a two-slide board review | a third slide that was cut, and a note the speaker was told not to say |
| [`odp/libreoffice-impress-hidden-slide.odp`](odp/libreoffice-impress-hidden-slide.md) | LibreOffice 24.2 Impress | the same deck | the same two, behind a style instead of an attribute |
| [`jpeg/imagemagick-stale-thumbnail.jpg`](jpeg/imagemagick-stale-thumbnail.md) | ImageMagick, exiftool 12.76 | a cropped photograph | the preview it was cropped from, still spelling the witness name |
| [`jpeg/imagemagick-thumbnail-regenerated.jpg`](jpeg/imagemagick-thumbnail-regenerated.md) | ImageMagick, exiftool 12.76 | the same crop | nothing — control |
| [`jpeg/imagemagick-no-thumbnail.jpg`](jpeg/imagemagick-no-thumbnail.md) | ImageMagick | the photograph before the crop | nothing, and a note saying there was no preview to compare — control |
| [`jpeg/exiftool-xmp-history.jpg`](jpeg/exiftool-xmp-history.md) | ImageMagick, exiftool 12.x | a flat panel with one word on it | an XMP edit history naming an application, two timestamps and the document it was derived from |
| [`jpeg/exiftool-xmp-absent.jpg`](jpeg/exiftool-xmp-absent.md) | ImageMagick | the same panel | nothing, and no packet to read — control |
| [`pdf/poppler-pdf-with-an-attachment.pdf`](pdf/poppler-pdf-with-an-attachment.md) | LibreOffice 24.2, poppler `pdfattach` | a decision notice naming no figure | a text file in `/Names/EmbeddedFiles` giving the reserve price |
| [`docx/libreoffice-writer-embedded-sheet.docx`](docx/libreoffice-writer-embedded-sheet.md) | LibreOffice 24.2 Writer | a summary with a small table pictured in it | the whole workbook behind the picture, as `word/embeddings/oleObject1.xlsx` |
| [`odt/libreoffice-writer-embedded-sheet.odt`](odt/libreoffice-writer-embedded-sheet.md) | LibreOffice 24.2 Writer | the same summary | the same workbook, as the sub-package `Object 1/` |
| [`pdf/pypdf-incremental-page-removed.pdf`](pdf/pypdf-incremental-page-removed.md) | LibreOffice 24.2, pypdf 6.16 | a one-page award notice | an earlier revision holding the annex that was deleted, reserve price and all |

Every specimen that hides text *on the page* is also found by `--ocr`, which
renders the page and reads the picture back and knows none of the mechanisms —
and every control stays silent under both. Two independent methods agreeing on
fourteen files is the strongest thing this directory has to say, and neither
could arrange it for the other.

The first two are failed redactions. The next two must not be reported, and for
different reasons: one was redacted correctly, the other has nothing to search.
The partial-bars file holds the detector honest about *how much* a bar covers.
The hidden-in-plain-sight file has nothing drawn over anything — everything it
hides, it hides by colour or by position — so every bar detector must stay
silent on it. The first DOCX is the tier-2 specimen, and every tier-2
detector fires on it exactly once. The second hides nothing by drawing or by
character: its deletions are text the application has agreed not to display.
The metadata pair is one source document in two containers, because the two
carry different amounts of the same metadata and a tool tried on one of them
would have a partial idea of what metadata is. The spreadsheet pair is the same
argument about hiding: OOXML writes it as an attribute on the thing hidden, ODF
puts a whole sheet's visibility behind a named style, and a reader that got
either wrong would disagree with the other. The .ods of that pair is also the
file that caught the worst bug this project has had - `unmasker` read its
hidden row, hidden column and hidden sheet as ordinary visible prose and then
reported the workbook clean.

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
- **XMP in a DOCX or a TIFF.** JPEG is covered by
  `exiftool-xmp-history.jpg`; those two containers carry packets as well and
  no file here holds one.
- **An angle other than 0 or 90 degrees**, and text rotated by a page's
  `/Rotate` entry rather than by the content stream. The grouping is general -
  it projects onto the text direction - but only the right angle is exercised
  by a producer.
- **Producers not on this machine.** Acrobat and Word draw their own way, and
  LibreOffice and Chrome already disagree with each other.
- **An annotation carrying an appearance stream.** Comments now have a
  specimen, but `/AP` is where a bar drawn as an annotation would live, and no
  producer here writes one — LibreOffice draws its shapes into the content
  stream, and a `/Square` written by hand renders in nothing without an `/AP`,
  which is precisely why the appearance stream is the part that matters. The
  tool notes such an annotation rather than passing over it.
- **A redaction that clips the second half of a line**, which is the hard
  case: evidence identical to `libreoffice-calc-clipped-overflow.pdf` and the
  opposite meaning. No producer here writes one, and the tool reports it
  exactly as it reports that file — which is correct, and is why the finding
  is weakened rather than filtered.
- **A clip that is not a rectangle**, and text clipped by a form XObject's
  `/BBox` rather than by a `W n` path.
- **A raster page with an invisible OCR text layer underneath**, which is a
  failed redaction that `flattened-to-image.pdf` does not represent.
- **A sheet marked `veryHidden`**, which the spreadsheet's own interface offers
  no way to undo. LibreOffice cannot set it in either format, so the reader
  handles it and only a synthetic test exercises it.
- **An `autoFilter` element**, which records what a filter was set to.
  LibreOffice's ODS writes none, and its .xlsx export drops the filter/hidden
  distinction altogether.
- **A 1904-epoch workbook**, a built-in `numFmtId` used without its format
  code, a time of day, and a conditional or coloured number format. Excel
  writes the first two routinely; LibreOffice defines every format explicitly
  and exports `date1904="false"`, so all four are covered only synthetically.
- **A tracked deletion that kept its cells.** Both formats allow the removed
  content to be stored with the deletion; neither producer here writes any, so
  a deletion always quotes nothing and the other path is untested.
- **A tracked insertion**, and a formatting-only revision (`rfmt`), which is
  the spreadsheet's `w:rPrChange`.
- **Excel and Word themselves.** Neither is on this machine, so every OOXML
  file here was written by LibreOffice.
- **PowerPoint itself**, and a presentation comment (`ppt/comments/`), which
  LibreOffice does not write. Decks were the one gap here that no amount of
  code could close - nothing on this machine could write one until
  `libreoffice-impress` was installed.
- **A slide with `show="1"`**, which PowerPoint writes and LibreOffice omits,
  and **a deck whose slide parts are numbered out of order**. Both are held by
  synthetic tests, because the specimen cannot tell the two implementations
  apart — and mutation testing is what said so.
- **Word's own OOXML.** Word is not on this machine, so every DOCX here was
  written by LibreOffice. It emits valid revision markup, but two producers
  never agree about everything — the PDF specimens proved that twice.
- **`w:moveFrom` / `w:moveTo` from a real producer.** LibreOffice does not emit
  move tracking; the reader handles it and only a synthetic test exercises it.
- **Nothing, on this front.** Every detector now fires on a committed file that
  a producer wrote, and `test_every_detector_now_has_a_specimen` holds that
  position. It was the gap that mattered most: a detector covered only by
  hand-built pages is exactly the shape of the bug that started this project.
