# `poppler-pdf-with-an-attachment.pdf`

**Producer:** LibreOffice 24.2 Writer for the page, poppler's `pdfattach` for
the attachment. Built by
[`sources/build_pdf_with_an_attachment.py`](../sources/build_pdf_with_an_attachment.py).

## What a person sees

One page. A decision notice saying the panel completed its evaluation, that the
contract was awarded on the merits of the submissions, and that nothing further
is disclosed at this stage. **No figure appears anywhere on it.**

## What is stored inside

One entry in `/Names/EmbeddedFiles`, named `panel-note.txt`, 109 bytes:

```
Reserve price: 240000 EUR.
Kowalski was told the reserve before bids closed.
Do not release with the notice.
```

No viewer shows it without being asked. Printing the notice does not print it.
The file travels with the document.

## Why this file exists

An attachment is not a hiding technique. It is a feature, used deliberately and
constantly — an invoice with its structured data, a report with the workbook
behind it — and the detector says so: *this is on no page and does not print
with the document*, and nothing more. What it means belongs to the reader.

That restraint is the point of the specimen. The content here is chosen so the
gap is obvious to a person reading the report, while the tool's own sentence
stays a statement about where the bytes are.

Everything is invented: no such tender, no such panel, no such bidder.

`pdfattach` writes the entry the way a real tool writes one, into the name
tree, with entries that may be indirect. Assembling one here from the
specification would prove the detector reads a structure this repository built,
which is the mistake `filetrail`'s HEIC reader was built on.

## The control

[`libreoffice-writer-metadata-leak.pdf`](libreoffice-writer-metadata-leak.md) —
the same producer with no attachment. The detector has to stay silent on it,
and a detector that fires on every PDF is worse than none.
