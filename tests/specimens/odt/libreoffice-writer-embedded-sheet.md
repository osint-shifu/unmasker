# `libreoffice-writer-embedded-sheet.odt`

**Producer:** LibreOffice 24.2 Writer. Built by
[`sources/build_embedded_object.py`](../sources/build_embedded_object.py).

## What a person sees

The same page as
[`libreoffice-writer-embedded-sheet.docx`](../docx/libreoffice-writer-embedded-sheet.md):
a paragraph disclosing no figures, and a small table rendered beneath it.

## What is stored inside

`Object 1/` — not a file but a **sub-package**: `content.xml`, `styles.xml`,
`settings.xml` and `manifest.rdf`, about 24 KB together, which is a complete
OpenDocument spreadsheet in its own right. `ObjectReplacements/Object 1` beside
it is the rendered picture and is deliberately not reported: that is what the
page shows, not what the file carries.

## Why this file exists

OpenDocument keeps an embedded object as a directory where OOXML keeps it as a
single member. Reporting it a member at a time would turn one object into four
findings, so the members are gathered and the object is reported once — the
same rule that stopped `low_contrast_text` reporting one hidden line as fifteen.

## A note on how it is built

The flat-ODF source has to be converted with the input filter named. The inner
`office:document` carries the spreadsheet's own mimetype, and left to detect the
type itself LibreOffice reads the whole file as a Calc document and the
conversion fails outright. That is recorded here because it cost the time it
cost, and because it is the sort of thing that looks like a broken specimen
rather than a filter argument.

Everything is invented.

## The control

The same as the DOCX: a document from this producer with no embedded object,
which the detector has to leave alone.
