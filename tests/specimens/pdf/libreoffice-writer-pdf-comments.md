# libreoffice-writer-pdf-comments.pdf

Two comments, still attached to the page and not part of it. `pdftotext`
reports neither.

- 18 411 bytes, `sha256:7d6d55b703e0dbff…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_pdf_with_comments.py \
    tests/specimens/pdf/libreoffice-writer-pdf-comments.pdf
```

LibreOffice **drops comments on PDF export by default**. It has to be asked:

```text
--convert-to 'pdf:writer_pdf_Export:{"ExportNotes":{"type":"boolean","value":"true"}}'
```

That is worth knowing on its own. A document can lose its comments on export
without anybody choosing that, and gain them the same way — and which of the
two happened is not visible from the page either.

## What a human sees

```text
BOARD MINUTE - SYNTHETIC

The board approved the revised terms without dissent.
The chair thanked the committee for its work.
```

## What is actually in the file

| annotation | author | text |
| --- | --- | --- |
| `/Text` | Anna Testowa, 19.04.2024 | `Only because the alternative was litigation. Do not minute this.` |
| `/Text` | Piotr Przyklad, 20.04.2024 | `Check whether the figure has to be disclosed at all.` |

Two `/Popup` annotations sit beside them. A popup is the window a comment
appears in, not the comment, and carries no text of its own.

## What this specimen was built to expose

Not a gap in the specimens — a **blind spot in the tool**. The interpreter read
the page's content stream and never looked at `/Annots` at all, so no amount of
content-stream work would ever have found a comment. It is the same class of
miss as reading a PDF's Info dictionary and never its XMP packet: the file
states things in more than one place, and reading one of them thoroughly is
not the same as reading the file.

The finding it produces carries the same detector name as a DOCX comment,
because it is the same statement about a document arriving through a wholly
different mechanism.

## The subtype that is deliberately not reported

`/FreeText` draws its contents *on the page*. A reader sees exactly what a
parser gets, so there is no gap — and a gap is the only thing this tool has to
say about anything. It is read and not reported, and that distinction has its
own test.

## What is still not read

**Appearance streams.** An annotation may carry an `/AP` form that paints
anything at all, including a black rectangle over text, and nothing here
interprets one. A bar drawn that way would be invisible to every detector in
this project.

It is not in this specimen because no producer on this machine writes one:
LibreOffice draws its shapes into the content stream, and a `/Square`
annotation written by hand renders in nothing — Ghostscript ignores it without
an `/AP`, which is exactly why the appearance stream is the thing that matters.
When such an annotation *does* carry one, the tool now says so in a note rather
than passing over it in silence.
