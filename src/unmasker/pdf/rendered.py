"""Rendering a page and reading the picture back.

This was deferred for most of the project's life, and the reason still holds:
it needs an OCR engine and a renderer, two heavy external binaries, and that
breaks *point it at a file, get an answer*. So nothing runs unless it is asked
for, and when the binaries are absent the tool says so and carries on - a
forensic tool that dies because an optional dependency is missing has made the
dependency compulsory.

## What it buys

Every other detector in this project knows a trick. `covered_text` knows about
filled paths, `invisible_text` about render modes and opacity,
`low_contrast_text` about colour. Each was written after a producer was caught
doing something particular, and each will miss whatever a producer invents
next.

This one knows nothing. It renders the page, reads the picture back, and asks
whether the words in the file are on it. A technique nobody has thought of
still fails that question - which is the only kind of detector that can.

## The coordinates

`gs` renders at a chosen resolution with the CropBox as the page, so a pixel is
`72/dpi` points and the origin is the top-left of the visible page.
`tesseract`'s TSV gives each word's box in those pixels. Mapping back to page
space is the same arithmetic the interpreter does for everything else, checked
against it: on the black-bars specimen the word `SYNTHETIC` comes back at
x 71.6, y 757.6-767.0, and the interpreter puts that run at x 71.0,
y 754.9-770.4.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .geometry import Rect

# 200 dpi is what a scanner produces and what tesseract is happiest with. Lower
# loses small type; higher costs time and buys very little.
DPI = 200

# How many consecutive words the file holds and the picture does not, before it
# is worth reporting. Measured, not chosen: across the specimens the
# properly-redacted control's longest such run is 2 - the labels beside its
# bars, which tesseract reads as `TT` and `ee` - and every file that hides
# something has a run of 5 or more. A single unread word is an OCR failure far
# more often than a concealment.
UNREAD_RUN = 3

# Below this, a word tesseract reports is more likely to be noise it found in
# an edge than text on the page. Used only when claiming the *page* shows
# something the file lacks, where a hallucination would be an invention.
CONFIDENT = 60.0


@dataclass(frozen=True)
class ReadWord:
    """One word tesseract read, placed in page space."""

    text: str
    bbox: Rect
    confidence: float


def tools_available(paths: dict[str, str | None] | None = None) -> tuple[bool, list[str]]:
    """Whether the binaries are here, and which are not.

    `paths` is for tests; by default the real `PATH` is consulted.
    """
    found = (
        paths if paths is not None else {name: shutil.which(name) for name in ("gs", "tesseract")}
    )
    missing = sorted(name for name, where in found.items() if not where)
    return (not missing), missing


def read_page_back(
    pdf: Path,
    number: int,
    box: Rect,
    *,
    dpi: int = DPI,
    renderer: str = "gs",
    engine: str = "tesseract",
) -> tuple[list[ReadWord], list[str]]:
    """Render page `number` and return the words an OCR engine reads off it.

    Never raises. Every failure - a missing binary, a renderer that will not
    render, an engine that produces nothing - comes back as a remark, because
    the alternative is a tool that stops working when an optional thing is
    absent.
    """
    remarks: list[str] = []
    for name in (renderer, engine):
        if not shutil.which(name):
            remarks.append(
                f"{name} is not on PATH, so the page could not be read back; "
                "reading it needs a renderer and an OCR engine"
            )
    if remarks:
        return [], remarks

    with tempfile.TemporaryDirectory(prefix="unmasker-render-") as tmp:
        image = Path(tmp) / "page.png"
        try:
            subprocess.run(
                [
                    renderer,
                    "-q",
                    "-dNOPAUSE",
                    "-dBATCH",
                    "-dSAFER",
                    "-dUseCropBox",
                    "-sDEVICE=png16m",
                    f"-r{dpi}",
                    f"-dFirstPage={number}",
                    f"-dLastPage={number}",
                    f"-sOutputFile={image}",
                    str(pdf),
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return [], [f"page {number} could not be rendered: {exc}"]

        if not image.exists():
            return [], [f"page {number} rendered to nothing"]

        try:
            tsv = subprocess.run(
                [engine, str(image), "stdout", "tsv"],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            ).stdout
        except (subprocess.SubprocessError, OSError) as exc:
            return [], [f"page {number} could not be read back: {exc}"]

    return _parse_tsv(tsv, box, dpi), []


def _parse_tsv(tsv: str, box: Rect, dpi: int) -> list[ReadWord]:
    """tesseract's TSV into page-space words.

    Pixels are `72/dpi` points, measured from the top-left of the *visible*
    page - the CropBox, which is what `-dUseCropBox` renders and what the
    interpreter calls the page box.
    """
    scale = 72.0 / dpi
    words: list[ReadWord] = []
    for line in tsv.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12 or not parts[11].strip():
            continue
        try:
            left, top, width, height = (int(parts[i]) for i in (6, 7, 8, 9))
            confidence = float(parts[10]) if parts[10] not in ("", "-1") else -1.0
        except ValueError:
            continue
        x0 = box.x0 + left * scale
        y1 = box.y1 - top * scale
        words.append(
            ReadWord(
                text=parts[11].strip(),
                bbox=Rect(x0, y1 - height * scale, x0 + width * scale, y1),
                confidence=confidence,
            )
        )
    return words
