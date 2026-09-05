# imagemagick-stale-thumbnail.jpg

A photograph cropped to remove a name, whose EXIF preview still shows it.

- 20 438 bytes
- produced by ImageMagick and exiftool 12.76

Its control is
[`imagemagick-thumbnail-regenerated.jpg`](imagemagick-thumbnail-regenerated.md):
the same crop with the preview made again.

## How it was made

```bash
python3 tests/specimens/sources/build_stale_thumbnail.py \
    tests/specimens/jpeg/imagemagick-stale-thumbnail.jpg \
    tests/specimens/jpeg/imagemagick-thumbnail-regenerated.jpg
```

## What a human sees

A picture 800×420 with a headline and a caption:

```text
Board photograph
Exhibit 4 - filed 2024-05-02
```

## What is actually in the file

| | |
| --- | --- |
| the picture | 800×420, aspect **1.90** |
| the preview in its EXIF | 160×120, aspect **1.33** |
| what OCR reads off the preview | `Board photograph`, **`WITNESS: A. TESTOWA`** |
| what OCR reads off the picture | `Board photograph`, `Exhibit 4 - filed 2024-05-02` |

The witness line is on the strip the crop removed. It is not on the picture and
it is in the file.

## What it is for

**Nobody had to be careless on purpose.** The specimen is built by cropping the
image with ImageMagick, and ImageMagick carries the old preview through
**unasked** — byte for byte, still describing a picture that no longer exists.
That is the whole reason this is worth detecting: it is the default behaviour
of an ordinary tool, not a trick.

**It is the first finding here with no text layer involved.** Every other
container answers *what does this document say that it does not show*. A
photograph says nothing, so the question inverts: *what does this file show
that the picture does not*.

**Two claims, and the specimen proves both are needed.**

The cheap one is arithmetic on headers: a JPEG states its own dimensions in a
marker, and the preview is a JPEG too, so a preview a different shape from its
picture was not made from it. No decoder, **no second dependency** — which
matters, because comparing pixels would have meant one, and `CONTRIBUTING.md`
requires that be argued for in writing.

The strong one costs an OCR pass and waits behind `--ocr`: read the preview and
report what is legible in it and absent from the picture. Here that is
`WITNESS: A. TESTOWA`, and it is `circumstantial` like every other reading-back
this tool does, because OCR is wrong constantly and its being wrong looks
exactly like concealment.

**Neither claim replaces the other.** A crop that happened to preserve the
aspect ratio would pass the first and fail the second. A camera that pads its
previews to a fixed size fails the first and would fail nothing.

**The threshold was measured, not chosen.** On the control the preview and the
picture disagree about **no** words at all, so one would have been enough; two
leaves room for a single misread without inventing a finding.

## What this specimen does not carry

- **A real camera's file.** Everything here is drawn by ImageMagick, so there
  is no maker-note block, no second preview, and no `PreviewImage` of the kind
  raw formats carry alongside the EXIF thumbnail.
- **TIFF, HEIC or PNG**, which carry previews of their own.
- **A crop that preserves the aspect ratio**, which only `--ocr` would catch.
- **A preview that is a *different photograph* entirely** rather than an
  earlier crop of the same one — the strongest version of this, and the one
  nobody produces by accident.
