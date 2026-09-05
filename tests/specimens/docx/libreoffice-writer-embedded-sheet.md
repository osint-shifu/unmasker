# `libreoffice-writer-embedded-sheet.docx`

**Producer:** LibreOffice 24.2 Writer, via a flat-ODF source converted twice.
Built by
[`sources/build_embedded_object.py`](../sources/build_embedded_object.py).

## What a person sees

A paragraph — *"Summary of the award. No figures are disclosed in this
paragraph."* — and beneath it a small table showing a reserve figure and a
name. The table is **a picture**: `word/media/image1.emf`, drawn by LibreOffice
so the object has something to render as.

## What is stored inside

`word/embeddings/oleObject1.xlsx` — a complete workbook, about 5.4 KB, which is
a zip archive in its own right. The picture was made from it; the file travels
with the document.

## Why this file exists

It is the second half of `attached-file`, and it makes a **different claim**
from the PDF specimen beside it, which is the reason it exists separately.

A PDF attachment is on no page. An embedded object *is* on the page — and what
is on the page is a rendering. Reporting this one as hidden would overstate it,
so the detector says the page shows a rendering rather than the file itself,
and the report's two columns follow: *human sees* a rendering of it, *machine
reads* a zip archive.

That second column matters. Saying "nothing in the file" about a file that is
plainly there is the kind of small lie this tool cannot afford, so where the
content cannot be quoted the report says what kind of thing it is, read from
the first bytes rather than from the name.

What the workbook holds is not read yet. A spreadsheet inside a document can
carry hidden sheets and filtered rows exactly as a spreadsheet on disk can, and
nothing here descends into it.

Everything is invented: no such award, no such panel.

## The control

[`libreoffice-writer-metadata-leak.docx`](libreoffice-writer-metadata-leak.md)
— the same producer, no embedded object, and the detector stays silent on it.
