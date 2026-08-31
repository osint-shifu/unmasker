# redacted-scan-with-ocr.pdf

A scan with a black box over the figure, and an invisible OCR layer underneath
that still spells it out. The box was painted on the picture *after* the text
layer was made, and the layer was never rebuilt.

- 35 449 bytes, `sha256:96b969d5230c5fcc…`
- `/Producer` `pypdf` — the last tool to write the file, which is the merge step

## How it was made

```bash
python3 tests/specimens/sources/build_redacted_scan_with_ocr.py \
    tests/specimens/pdf/redacted-scan-with-ocr.pdf
```

Five producers, none of them this project:

| | |
| --- | --- |
| LibreOffice | writes the page |
| Ghostscript | rasterises it at 200 dpi, as a scanner would |
| tesseract 5.3.4 | reads the picture and writes the invisible text layer |
| ImageMagick | paints the black box on the picture, after the OCR |
| pypdf | lays the redacted picture over the original |

The box goes where `pdftotext -bbox` says the figure is, converted to pixels at
the raster's own resolution — measured by poppler, as every other specimen's
geometry is.

## What a human sees

```text
SETTLEMENT MEMORANDUM - SYNTHETIC
Agreed figure: ████
Signed on 17 April 2024 by both parties.
```

## What is actually in the file

```text
SETTLEMENT MEMORANDUM - SYNTHETIC
Agreed figure: 250,000 EUR
Signed on 17 April 2024 by both parties.
```

Confirmed with `pdftotext`, which is not this project's code.

## Why the order of operations is the whole point

A searchable scan is a picture of a page with a text layer underneath, drawn in
render mode 3 so that none of it appears on screen. That layer is why a scan
can be searched and copied from, and every OCR pipeline produces one.

Redacting the *picture* does not touch the *layer*. There is no visual
difference between a scan with an accurate text layer and a scan with a stale
one, so nothing about the page tells anybody that the figure is still there.

This is the case `flattened-to-image.pdf` deliberately does *not* represent —
that one has no text layer at all, and its provenance says so and names this
file's shape as the nastier one. It now exists.

## What this specimen broke

It was built to give `invisible-text` a specimen from a real producer, and the
first report it produced had **sixteen findings, one per word**.

tesseract writes one show-operation per word. `invisible_text` was still
working per run, which is exactly the mistake `covered_text` made with Chrome —
Chrome writes one operation per *glyph*, and a per-run detector turned one
black bar into eighty-seven findings. The same fix applies: group by line on
the page, not by whatever unit the producer chose.

Three findings now, one per line.

## A detail the specimen does not exercise

tesseract writes a trailing space inside each word's operation, so joining its
glyphs needs no help. Chrome does not, and neither do many others: the gap
between two operations is in the positioning and nothing else. Restoring it is
in the code and only a synthetic page tests it, because on this file the
guard against double-spacing is doing all the work.
