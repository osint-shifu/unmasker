#!/usr/bin/env python3
"""Build the JPEG-carries-XMP specimen.

XMP is not a PDF thing. A photograph carries the same packet, and what it
carries is often an **edit history**: what this file was derived from, which
application touched it, and when. `xmpMM:History` is written by editors as a
matter of course, survives every save, and appears nowhere on the picture.

That is the whole finding. A person sees an image. Every XMP reader sees that
the image was derived from another document and saved twice by a named
application on named dates.

Measured on the file this script writes:

    picture            400 x 300, a flat panel with one word on it
    xmpMM:History      two events, `derived` then `saved`
    softwareAgent      Adobe Photoshop 25.0 (Windows)
    DerivedFromDocumentID  present

Nothing on the picture states any of it. Everything in it is invented - there
is no such document, no such edit, and the software agent names an application
that never touched this file. `exiftool` writes the packet; nothing here is
assembled by hand, because a packet built to match the specification proves
nothing about the packets real editors write.

## The control

The same picture with no XMP at all, so the detector has to stay silent on it.
Without that this specimen shows a reader firing, not a reader being right.

Usage:

    python3 tests/specimens/sources/build_xmp_in_a_photograph.py tests/specimens/jpeg
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORD = "PRZYKLAD"

HISTORY = [
    "-XMP-xmpMM:DerivedFromDocumentID=xmp.did:8f1c2a6b-nie-istnieje",
    "-XMP-xmpMM:HistoryAction=derived",
    "-XMP-xmpMM:HistoryAction+=saved",
    "-XMP-xmpMM:HistorySoftwareAgent=Adobe Photoshop 25.0 (Windows)",
    "-XMP-xmpMM:HistorySoftwareAgent+=Adobe Photoshop 25.0 (Windows)",
    "-XMP-xmpMM:HistoryChanged=/metadata",
    "-XMP-xmpMM:HistoryChanged+=/",
    "-XMP-xmpMM:HistoryWhen=2026-02-11T09:14:00+01:00",
    "-XMP-xmpMM:HistoryWhen+=2026-02-11T09:31:00+01:00",
]


def draw(path: Path) -> None:
    subprocess.run(
        [
            "convert", "-size", "400x300", "xc:#4a6a8a",
            "-pointsize", "28", "-fill", "white",
            "-annotate", "+40+160", WORD,
            str(path),
        ],
        check=True,
    )


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    carrying = out / "exiftool-xmp-history.jpg"
    draw(carrying)
    subprocess.run(
        ["exiftool", "-overwrite_original", "-q", *HISTORY, str(carrying)], check=True
    )

    # The control. `convert` writes no XMP of its own, so this is simply the
    # picture with the packet never added.
    bare = out / "exiftool-xmp-absent.jpg"
    draw(bare)

    for path in (carrying, bare):
        print(f"{path}  {path.stat().st_size} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/jpeg"))
