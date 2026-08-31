# libreoffice-writer-image-over-text.pdf

The redaction is a picture. Someone pasted a black rectangle *as an image* over
a name and exported. It looks exactly like a drawn bar and is nothing like one
in the file.

- 21 602 bytes, `sha256:d324105840b72c0d…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

```bash
python3 tests/specimens/sources/build_image_over_text.py \
    tests/specimens/pdf/libreoffice-writer-image-over-text.pdf
```

Two passes, like the black-bar builder and for the same reason: the picture
goes where `pdftotext -bbox` says the name is, not where a guess would put it.
ImageMagick makes the black raster; LibreOffice places it as a
`<draw:frame>` with `style:run-through="foreground"`, which is the same line
that makes the drawn-bar specimen a failed redaction rather than a background.

## What a human sees

```text
PERSONNEL NOTE - SYNTHETIC

Reference:   SYN-2024-1102
Subject:     ████████████████
Outcome:     no further action
```

## What is actually in the file

`Ludmila Wieczorek-Test`, in the text layer, read straight out by `pdftotext`.

## Why it needs to exist separately

There is no path here. No fill colour, no `re`, no `f*`, nothing for the
graphics state to track — an image XObject, placed by a transformation matrix.
Every shape-based detector in this tool finds nothing on this file, and
`covered_text` is asserted to stay silent on it.

The specimens README has listed "redaction by image, annotation or clipping
path" as untested since task 1. This closes the first of those three.

## The innocent explanation, named

`text-under-image` is a separate detector from `covered-text` because an image
over a text layer is also exactly what a scan of a printed page is, and there
the two normally agree. The finding says so rather than implying a motive:

```text
● 22 characters under an image at x 123.3-245.9, y 702.8-720.0; an image over
  a text layer is also what a scan of a printed page looks like, and there the
  two normally agree
```

[`redacted-scan-with-ocr.pdf`](redacted-scan-with-ocr.md) is the specimen where
they do *not* agree.

## What it completes

Before this file, `text-under-image` was the last detector covered only by unit
tests on hand-built pages — no producer had ever written a file it fired on.
That is exactly the shape of the bug that started this project: a detector that
agrees with the specification and with nothing any producer emits.
`test_every_detector_now_has_a_specimen` holds the position.
