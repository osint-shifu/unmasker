#!/usr/bin/env python3
"""Build the specimen the tool must decline to judge.

A band of picture across the top of a page and a line of white text sitting on
it. Whether that text is readable depends on what colour the picture is exactly
where the glyphs are, and the content stream does not say: an image is a
rectangle of pixels placed by a matrix, and nothing short of rendering it finds
out what is at any point inside.

So `low-contrast-text` reports nothing here, and that is the right answer. What
would be wrong is the answer it used to give. `_background` only looked at
filled shapes, so it found none behind these glyphs, fell through to "the
background is the paper, and the paper is white", and reported white text on
white - a conclusion about a picture it had never looked at.

The file is therefore a control, and its value is in the second half of what
the tool says about it: a note that there is text on an image and that the
comparison could not be made. `CONTRIBUTING.md`: "nothing found" has two meanings,
and a reader who cannot tell them apart has been told something the tool never
established.

Everything is invented.

Usage:
    python3 build_text_on_an_image.py OUTPUT.pdf [--workdir DIR]
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

ON_THE_IMAGE = "Reference copy - not for circulation"
VISIBLE = "This line is ordinary black text on the paper and must not be reported."
CLOSING = "One line above sits on the picture. Its legibility is not in this file."


def fodt(image: Path | None, box: dict | None) -> str:
    frame = ""
    if image and box:
        frame = (
            f'<draw:frame text:anchor-type="page" text:anchor-page-number="1"'
            f' draw:style-name="Behind" draw:z-index="0"'
            f' svg:x="{box["x"]:.3f}cm" svg:y="{box["y"]:.3f}cm"'
            f' svg:width="{box["w"]:.3f}cm" svg:height="{box["h"]:.3f}cm">'
            f'<draw:image xlink:href="{image.as_uri()}" xlink:type="simple"'
            f' xlink:show="embed" xlink:actuate="onLoad"/>'
            f"</draw:frame>"
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
  <style:style style:name="Body" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.4cm"/>
   <style:text-properties fo:font-size="12pt"/>
  </style:style>
  <style:style style:name="White" style:family="text">
   <style:text-properties fo:color="#ffffff"/>
  </style:style>
  <style:style style:name="Behind" style:family="graphic">
   <style:graphic-properties draw:stroke="none" fo:border="none"
    fo:padding="0cm" style:run-through="background" style:wrap="run-through"
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
  <text:p text:style-name="Head">{frame}TEXT ON A PICTURE - SYNTHETIC</text:p>
  <text:p text:style-name="Body">{VISIBLE}</text:p>
  <text:p text:style-name="Body"><text:span
   text:style-name="White">{ON_THE_IMAGE}</text:span></text:p>
  <text:p text:style-name="Body">{CLOSING}</text:p>
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
            x0 = min(w[0] for w in window) - 8
            y0 = min(w[1] for w in window) - 4
            x1 = max(w[2] for w in window) + 8
            y1 = max(w[3] for w in window) + 4
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

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-onimage-"))
    tmp.mkdir(parents=True, exist_ok=True)

    print("pass 1: exporting the text alone, to find where the line lands")
    clean = export(fodt(None, None), tmp, "pass1-text-only")
    box = box_over(clean, ON_THE_IMAGE)
    print(f"        the line is at {box['x']:.2f},{box['y']:.2f}cm")

    # Something with structure, so no single colour is the honest answer for
    # the whole of it. A flat rectangle would have one, and a flat rectangle is
    # what `low-contrast-text` already handles.
    picture = tmp / "band.png"
    subprocess.run(
        ["convert", "-size", "640x80", "plasma:navy-steelblue", str(picture)],
        check=True,
        capture_output=True,
        timeout=120,
    )

    print("pass 2: exporting with the picture behind it")
    final = export(fodt(picture, box), tmp, "pass2-on-image")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
