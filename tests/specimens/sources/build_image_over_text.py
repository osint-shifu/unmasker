#!/usr/bin/env python3
"""Build the specimen where the redaction is a picture rather than a shape.

Someone opens a document, pastes a black rectangle *as an image* over a name,
and exports. The result looks exactly like a drawn bar and is nothing like one
in the file: there is no path, no fill colour, no `re` and no `f*` - just an
image XObject placed by a transformation matrix.

Every shape-based detector in this tool would find nothing. The specimens
README has listed "redaction by image" as untested since task 1.

It is also the one case where the innocent explanation is common enough to have
to be said out loud: a page image over a text layer is what a scan of a printed
page looks like, and there the two normally agree. So the finding names it, and
`redacted-scan-with-ocr.pdf` is the specimen where they do not.

Two passes, as the black-bar builder does, and for the same reason: the picture
is placed on poppler's measurement of where the words are, not on a guess.

Everything is invented.

Usage:
    python3 build_image_over_text.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CM_PER_PT = 2.54 / 72.0

COVERED = "Ludmila Wieczorek-Test"
FIELDS = [
    ("Reference", "SYN-2024-1102"),
    ("Subject", COVERED),
    ("Outcome", "no further action"),
]
HEADING = "PERSONNEL NOTE - SYNTHETIC"
CLOSING = "Circulated to the panel only."


def fodt(image: Path | None, box: dict | None) -> str:
    """The document, with the picture laid over the name once it is measured.

    `style:run-through="foreground"` is what puts the picture in front of the
    text instead of behind it - the same line that makes the drawn-bar specimen
    a failed redaction rather than a background.
    """
    frame = ""
    if image and box:
        frame = (
            f'<draw:frame text:anchor-type="page" text:anchor-page-number="1"'
            f' draw:style-name="Over" draw:z-index="10"'
            f' svg:x="{box["x"]:.3f}cm" svg:y="{box["y"]:.3f}cm"'
            f' svg:width="{box["w"]:.3f}cm" svg:height="{box["h"]:.3f}cm">'
            f'<draw:image xlink:href="{image.as_uri()}" xlink:type="simple"'
            f' xlink:show="embed" xlink:actuate="onLoad"/>'
            f"</draw:frame>"
        )

    rows = "".join(
        f'<text:p text:style-name="Field">{label}:'
        + "&#160;" * max(1, 12 - len(label))
        + f"{value}</text:p>"
        for label, value in FIELDS
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="Head" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.5cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Field" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.3cm"/>
   <style:text-properties fo:font-size="12pt"/>
  </style:style>
  <style:style style:name="Over" style:family="graphic">
   <style:graphic-properties draw:stroke="none" fo:border="none"
    fo:padding="0cm" style:run-through="foreground" style:wrap="run-through"
    style:vertical-pos="from-top" style:vertical-rel="page"
    style:horizontal-pos="from-left" style:horizontal-rel="page"/>
  </style:style>
  <style:page-layout style:name="PL">
   <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"
    fo:margin-top="2.5cm" fo:margin-bottom="2cm"
    fo:margin-left="2.5cm" fo:margin-right="2.5cm"/>
  </style:page-layout>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="PL"/>
 </office:master-styles>
 <office:body><office:text>
  <text:p text:style-name="Head">{frame}{HEADING}</text:p>
  {rows}
  <text:p text:style-name="Field">{CLOSING}</text:p>
 </office:text></office:body>
</office:document>
"""


def export(text: str, workdir: Path, stem: str) -> Path:
    src = workdir / f"{stem}.fodt"
    src.write_text(text, encoding="utf-8")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{workdir / 'loprofile'}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(workdir),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    out = workdir / f"{stem}.pdf"
    if not out.exists():
        raise RuntimeError(f"LibreOffice produced no PDF for {src}")
    return out


def box_over(pdf: Path, value: str) -> dict:
    """Where poppler puts these words, in centimetres from the page's top-left."""
    out = subprocess.run(
        ["pdftotext", "-bbox", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout
    pattern = (
        r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>'
    )
    words = [
        (float(a), float(b), float(c), float(d), html.unescape(e))
        for a, b, c, d, e in re.findall(pattern, out)
    ]
    pieces = value.split()
    for start in range(len(words) - len(pieces) + 1):
        window = words[start : start + len(pieces)]
        if [w[4] for w in window] == pieces:
            x0 = min(w[0] for w in window) - 2
            y0 = min(w[1] for w in window) - 2
            x1 = max(w[2] for w in window) + 2
            y1 = max(w[3] for w in window) + 2
            return {
                "x": x0 * CM_PER_PT,
                "y": y0 * CM_PER_PT,
                "w": (x1 - x0) * CM_PER_PT,
                "h": (y1 - y0) * CM_PER_PT,
            }
    raise RuntimeError(f"poppler did not report the words of {value!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-image-"))
    tmp.mkdir(parents=True, exist_ok=True)

    print("pass 1: exporting the text alone, to find where the name lands")
    clean = export(fodt(None, None), tmp, "pass1-text-only")
    box = box_over(clean, COVERED)
    print(f"        the name is at {box['x']:.2f},{box['y']:.2f}cm, {box['w']:.2f}cm wide")

    # A plain black raster, which is what a pasted redaction actually is.
    patch = tmp / "patch.png"
    subprocess.run(
        ["convert", "-size", "600x60", "xc:black", str(patch)],
        check=True,
        capture_output=True,
        timeout=120,
    )

    print("pass 2: exporting with the picture over it")
    final = export(fodt(patch, box), tmp, "pass2-covered")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
