# imagemagick-thumbnail-regenerated.jpg

The control. The same crop as
[`imagemagick-stale-thumbnail.jpg`](imagemagick-stale-thumbnail.md), with the
preview made again from what is actually in the frame.

- 22 296 bytes
- produced by ImageMagick and exiftool 12.76

## What is in the file

| | |
| --- | --- |
| the picture | 800×420, aspect 1.90 |
| the preview in its EXIF | 160×84, aspect 1.90 |
| what OCR reads off the preview | `Board photograph` — and nothing the picture does not also say |

## What it is for

**Nothing.** That is its job, and it is why the other specimen is worth
anything.

A detector that reports a stale preview proves it fires. It does not prove it
is right, and a detector that fired on every photograph ever cropped would be
worse than none — this is a file format where nearly every picture on a phone
carries a preview, so a false positive here is a report nobody finishes.

This file must stay silent under both claims: the shapes agree to within
rounding, and OCR reads nothing off the preview that is not also on the
picture. `test_a_regenerated_thumbnail_is_not_reported` and
`test_ocr_stays_silent_on_the_control` hold it.

It is also where the OCR threshold came from. On this file the preview and the
picture disagree about **no** words, which is what makes two a safe line rather
than a guess.

## What this specimen does not carry

- **A near miss.** The two aspect ratios here are equal to within the rounding
  of scaling to whole pixels, and nothing exercises the tolerance at its edge.
