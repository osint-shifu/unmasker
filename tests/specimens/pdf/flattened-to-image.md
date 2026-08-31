# flattened-to-image.pdf

**A control for the second meaning of "nothing found".** This page has no text
layer at all. There is nothing to search, which is a different finding from
having searched and found nothing, and a reader who confuses the two has drawn a
conclusion the tool never supported.

- 16 653 bytes, `sha256:665ffa894cd1dda3…`
- no `/Producer`

## How it was made

Ghostscript, rasterising the failed-redaction specimen at 150 dpi:

```bash
gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfimage24 -r150 \
   -sOutputFile=tests/specimens/pdf/flattened-to-image.pdf \
   tests/specimens/pdf/libreoffice-writer-black-bars.pdf
```

Flattening is how a redaction that started out failed becomes a redaction that
actually holds, and it is a common last step in real release workflows —
print to image, or export at reduced fidelity, and the hidden layer goes with
it.

## What a human sees

The same page as `libreoffice-writer-black-bars.pdf`, at 150 dpi. Four black
bars, two readable fields.

## What is actually in the file

One image. Resources carry `/XObject` `['/Im1']` and `/Font` `[]` — no fonts,
therefore no text objects. `extract_text()` returns `''` and `pdftotext`
returns nothing.

## What it is for

The tool must not say "no hidden text found" about this file. There is no text
here to hide, and the honest report says so: the page has no text layer, so the
question of what is under the bars cannot be answered from the text — it would
need OCR, which `HANDOFF.md` records as deferred.

`filetrail` grew a `doctor` command for exactly this distinction. Expect to need
the equivalent, and expect this specimen to be the test for it.

Note what this control does *not* cover: a page flattened to an image with an
invisible OCR text layer laid underneath, which is what a scanner or a
"searchable PDF" pipeline produces. That is a failed redaction again, and a
nastier one. It needs its own specimen.
