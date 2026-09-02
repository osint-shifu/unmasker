# text-on-an-image.pdf

A band of picture across the page and a line of white text sitting on it. The
tool reports nothing, and says why.

- 34 476 bytes, `sha256:4f3c901a3779b28f…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_text_on_an_image.py \
    tests/specimens/pdf/text-on-an-image.pdf
```

Two passes, with the picture placed on poppler's measurement of where the line
lands. The picture is `plasma:navy-steelblue` from ImageMagick, deliberately
not a flat colour: a flat rectangle has an honest single answer, and a flat
rectangle is what `low-contrast-text` already handles.

## What a human sees

```text
TEXT ON A PICTURE - SYNTHETIC

This line is ordinary black text on the paper and must not be reported.

▓▓ Reference copy - not for circulation ▓▓      ← white on a blue picture

One line above sits on the picture. Its legibility is not in this file.
```

## What the tool says

Nothing found — and a note:

```text
page 1 has 31 characters sitting on a picture or on a fill this file does not
state plainly; whether they can be read there was not established, because
what colour it is where they sit is not in the content stream
```

## Why silence is the right answer here

Whether that line is readable depends on what colour the picture is *exactly
where the glyphs are*. An image in a PDF is a rectangle of pixels placed by a
matrix; nothing short of rendering it finds out what is at any point inside.
On this file a reader can see the text plainly. On the same file with a paler
picture they could not. The content stream is identical either way.

## The bug this specimen was built to catch

`_background` only looked at *filled shapes*. Behind these glyphs there is no
fill, so it found none, fell through to "the background is the paper, and the
paper is white", and reported **white text on white — the same colour**.

That is the tool stating a conclusion about a picture it had never looked at,
and its own docstring already said not to: *"we cannot tell what is behind
this" and "it is white" are different answers, and only one of them is true.*
The rule was written for fills with an unreadable colour and never extended to
images.

## Why the note matters more than the silence

`CONTRIBUTING.md`: **"nothing found" has two meanings.** *Searched, and it is not
there* is one. *There was nothing this tool could search* is the other, and a
reader who cannot tell them apart has been told something the tool never
established.

This file is the second meaning for a detector rather than for a whole page —
`flattened-to-image.pdf` is the page-level version — and the note is what keeps
them apart. Exit status is 0, which is correct: nothing was found. The note is
what stops that reading as *nothing is there*.
