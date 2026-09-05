"""The preview that still shows what was cropped out.

A photograph carries a small copy of itself in its EXIF, for a camera's screen
and a file browser's grid. **Cropping the photograph does not regenerate it.**
Cut a face, a name or a plate out of a picture and the preview in the file
still shows the frame you cut it out of.

This is not a reading of the specification. ImageMagick carries the old preview
through a crop unasked, which is how the specimen is built and why this is
worth detecting at all: nobody has to be careless on purpose.

## Two claims, and only one of them is cheap

**The shapes disagree.** A JPEG states its own dimensions in a marker, and the
preview is a JPEG too, so this is header arithmetic - no decoder, no second
dependency, no rendering. A preview a different shape from its picture was not
made from it. It is `circumstantial`: a camera may pad a preview to a fixed
size, and a crop that happens to preserve the aspect ratio slips through.

**The preview still spells what the picture does not.** That is the strong
version and it costs an OCR pass, so it lives behind `--ocr` like every other
reading-it-back this tool does - and, like them, it can never be `direct`,
because OCR is wrong constantly and its being wrong looks exactly like
concealment.

The two are different claims about the same file and neither replaces the
other. A regenerated preview of a cropped picture passes the first and would
fail nothing; a stale preview that kept its aspect ratio fails only the second.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .findings import Basis, Finding, Location
from .jpeg import Jpeg

#: How far two aspect ratios may differ before the preview is taken not to have
#: come from the picture. A percent of slack absorbs the rounding a thumbnail
#: picks up from being scaled to whole pixels - 160x84 against 800x420 is not
#: exactly equal - without admitting a real crop, which changes the ratio by
#: tens of percent.
TOLERANCE = 0.02

#: Words tesseract is less sure of than this are noise it found in the paper.
#: The same number `pdf/rendered.py` measured, for the same reason.
CONFIDENT = 60.0

#: How many confident words the preview must hold that the picture does not,
#: before it is reported. Measured rather than chosen: on the regenerated
#: control the preview and the picture disagree about **nothing**, so one would
#: do; two leaves room for a single misread word without inventing a finding.
UNSEEN_WORDS = 2


def stale_thumbnail(jpeg: Jpeg) -> list[Finding]:
    """A preview whose shape says it was made from a different picture."""
    if jpeg.size is None or jpeg.thumbnail_size is None:
        return []

    picture, preview = jpeg.size, jpeg.thumbnail_size
    if not picture.aspect or not preview.aspect:
        return []
    if abs(picture.aspect - preview.aspect) / picture.aspect <= TOLERANCE:
        return []

    return [
        Finding(
            detector="stale-thumbnail",
            basis=Basis.CIRCUMSTANTIAL,
            summary=(
                f"the picture is {picture} and the preview in its EXIF is "
                f"{preview}, which is a different shape - so the preview was "
                "not made from this picture, and shows whatever was in frame "
                "when it was"
            ),
            human_sees=f"a picture {picture}",
            machine_reads=f"a preview {preview}, of something else",
            location=Location(),
        )
    ]


def _words(image: Path, engine: str = "tesseract") -> tuple[list[str], list[str]]:
    """What an OCR engine reads off one image, and what went wrong."""
    try:
        tsv = subprocess.run(
            [engine, str(image), "stdout", "tsv"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        ).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        return [], [f"{image.name} could not be read back: {exc}"]

    out = []
    for line in tsv.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            confidence = float(parts[10])
        except ValueError:
            continue
        text = parts[11].strip()
        if text and confidence >= CONFIDENT:
            out.append(text)
    return out, []


def _normalised(words: list[str]) -> set[str]:
    """Lowercased and stripped of punctuation, because `TESTOWA` and
    `TESTOWA,` are the same word and only one of them would match."""
    return {"".join(c for c in word.lower() if c.isalnum()) for word in words} - {""}


def unseen_in_the_picture(
    picture: Path, jpeg: Jpeg, engine: str = "tesseract"
) -> tuple[list[Finding], list[str]]:
    """Words legible in the preview and absent from the picture itself.

    Never raises. A missing binary or an engine that produces nothing comes
    back as a remark, because a tool that stops working when an optional thing
    is absent has made it compulsory.
    """
    if not jpeg.thumbnail:
        return [], []
    if not shutil.which(engine):
        return [], [f"{engine} is not on PATH, so the preview was not read back"]

    with tempfile.TemporaryDirectory(prefix="unmasker-thumb-") as tmp:
        folder = Path(tmp)
        preview = folder / "preview.jpg"
        preview.write_bytes(jpeg.thumbnail)

        in_preview, problems = _words(preview)
        in_picture, more = _words(picture)
        problems += more

    unseen = [w for w in in_preview if "".join(c for c in w.lower() if c.isalnum())
              not in _normalised(in_picture)]
    unseen = [w for w in unseen if "".join(c for c in w if c.isalnum())]

    if len(unseen) < UNSEEN_WORDS:
        return [], problems

    return [
        Finding(
            detector="unrendered-text",
            basis=Basis.CIRCUMSTANTIAL,
            summary=(
                f"{len(unseen)} words are legible in the preview inside this "
                "file and are not on the picture itself; OCR is wrong often "
                "enough that this is a reading rather than a certainty"
            ),
            human_sees="",
            machine_reads=" ".join(unseen),
            location=Location(),
        )
    ], problems


def detect(picture: Path, jpeg: Jpeg, ocr: bool = False) -> tuple[list[Finding], list[str]]:
    findings = stale_thumbnail(jpeg)
    remarks: list[str] = []
    if ocr:
        found, problems = unseen_in_the_picture(picture, jpeg)
        findings += found
        remarks += problems
    return findings, remarks
