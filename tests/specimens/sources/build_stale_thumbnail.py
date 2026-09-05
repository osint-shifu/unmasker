#!/usr/bin/env python3
"""Build the stale-thumbnail specimen.

A photograph carries a small copy of itself in its EXIF, for a camera's own
screen and for a file browser's grid. **Cropping the photograph does not
regenerate it.** Cut a face, a name or a licence plate out of a picture, and
the preview in the file still shows the frame you cut it out of.

This is not a trick anybody has to be clever about, and it is not a reading of
the specification. ImageMagick does it **unasked**, which is how this specimen
is built: crop the image and the thumbnail comes through untouched, byte for
byte, still describing a picture that no longer exists.

Measured on the file this script writes:

    image      800 x 420   aspect 1.90
    thumbnail  160 x 120   aspect 1.33
    OCR of the thumbnail   WITNESS: A. TESTOWA

That last line is on the strip that was cropped away. A person opening the
photograph cannot see it; every EXIF reader can.

## Why the picture says what it says

The witness line is set large, dark red, and low in the frame - the part that
gets cropped. Big enough that `tesseract` can still read it after the picture
has been reduced to 160 pixels wide, because the specimen has to prove the
finding is *legible* rather than merely present. A watermark nobody could read
back would be a weaker claim wearing the same words.

Everything is invented.

## The control

The same crop, with the thumbnail regenerated afterwards - which is what a
careful editor does and what the detector must stay silent about. Without it
this specimen proves a detector fires, not that it is right, and a detector
that fires on every photograph ever cropped is worse than none.

Usage:
    python3 build_stale_thumbnail.py OUTPUT.jpg CONTROL.jpg [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WIDTH, HEIGHT = 800, 600
KEPT = 420  # the crop keeps the top of the frame

HEADLINE = "Board photograph"
CAPTION = "Exhibit 4 - filed 2024-05-02"
WITNESS = "WITNESS: A. TESTOWA"


def _run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


def build(target: Path, control: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-thumb-"))
    scratch.mkdir(parents=True, exist_ok=True)

    full = scratch / "full.jpg"
    thumb = scratch / "thumb.jpg"
    cropped = scratch / "cropped.jpg"

    # The photograph as it was taken: the witness line sits low, where a crop
    # will take it.
    _run(
        "convert",
        "-size",
        f"{WIDTH}x{HEIGHT}",
        "xc:#d8d8d0",
        "-pointsize",
        "44",
        "-fill",
        "#202020",
        "-annotate",
        "+40+90",
        HEADLINE,
        "-pointsize",
        "26",
        "-fill",
        "#4a4a4a",
        "-annotate",
        "+40+150",
        CAPTION,
        "-pointsize",
        "52",
        "-fill",
        "#8b1a1a",
        "-annotate",
        f"+40+{HEIGHT - 80}",
        WITNESS,
        str(full),
    )

    # The preview a camera would have written, made from the whole frame.
    _run("convert", str(full), "-resize", "160x120", str(thumb))
    _run(
        "exiftool",
        "-overwrite_original",
        f"-ThumbnailImage<={thumb}",
        "-Make=TestCam",
        "-Model=TC-1",
        str(full),
    )

    # The crop. Nothing here asks for the thumbnail to be kept - ImageMagick
    # carries it through on its own, which is the entire point.
    _run("convert", str(full), "-crop", f"{WIDTH}x{KEPT}+0+0", "+repage", str(cropped))

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(cropped, target)
    print(f"wrote {target} ({target.stat().st_size} bytes)")

    # The control: the same crop, with the preview made again from what is
    # actually in the frame now. This is what a careful editor does, and the
    # detector has to stay silent about it.
    fresh_thumb = scratch / "fresh.jpg"
    honest = scratch / "honest.jpg"
    shutil.copy(cropped, honest)
    _run("convert", str(honest), "-resize", "160x84", str(fresh_thumb))
    _run("exiftool", "-overwrite_original", f"-ThumbnailImage<={fresh_thumb}", str(honest))
    control.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(honest, control)
    print(f"wrote {control} ({control.stat().st_size} bytes)")

    if workdir is None:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("control", type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    build(args.output, args.control, args.workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
