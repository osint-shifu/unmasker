#!/usr/bin/env python3
"""Build the specimen that sits on the edge of what counts as covered.

Every bar in every other specimen stops in the gap between two words, so no
glyph is ever half covered and the question never arises. This one asks it four
times over: four single-character marks on a line, under four bars covering
100%, 75%, 50% and 25% of them.

A threshold has to be somewhere. Wherever it is, a document exists that sits
just the wrong side of it, and the only honest thing is to have a file that
says where this tool's actually is - so that changing it is a decision somebody
makes rather than a number that drifts.

The marks are single characters and space-separated, so `pdftotext -bbox`
reports a box for each one on its own. That is what makes a fraction of a
*glyph* measurable without per-glyph geometry from this project's own code: a
one-character word's box is a glyph's box.

Everything is invented.

Usage:
    python3 build_coverage_edge.py OUTPUT.pdf [--workdir DIR]
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

# Mark, and the fraction of its width the bar covers, measured from its left.
MARKS = [("A", 1.00), ("B", 0.75), ("C", 0.50), ("D", 0.25)]

HEADING = "COVERAGE EDGE - SYNTHETIC"
LINE = "Marks: " + " ".join(mark for mark, _ in MARKS)
CLOSING = "Each mark above is covered by a different fraction of a bar."


def fodt(bars: list[dict]) -> str:
    shapes = "".join(
        f'<draw:custom-shape text:anchor-type="page" text:anchor-page-number="1"'
        f' draw:style-name="Bar" draw:z-index="{10 + i}"'
        f' svg:x="{b["x"]:.4f}cm" svg:y="{b["y"]:.4f}cm"'
        f' svg:width="{b["w"]:.4f}cm" svg:height="{b["h"]:.4f}cm">'
        f'<draw:enhanced-geometry draw:type="rectangle"/>'
        f"</draw:custom-shape>"
        for i, b in enumerate(bars)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="Head" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.6cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Body" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.4cm"/>
   <style:text-properties fo:font-size="16pt"/>
  </style:style>
  <style:style style:name="Bar" style:family="graphic">
   <style:graphic-properties draw:fill="solid" draw:fill-color="#000000"
    draw:stroke="none" style:run-through="foreground" style:wrap="run-through"
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
  <text:p text:style-name="Head">{shapes}{HEADING}</text:p>
  <text:p text:style-name="Body">{LINE}</text:p>
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


def bars_over(pdf: Path) -> list[dict]:
    """One bar per mark, each covering its stated fraction of poppler's box."""
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

    marks = {name: None for name, _ in MARKS}
    for word in words:
        if word[4] in marks and marks[word[4]] is None:
            marks[word[4]] = word
    missing = [name for name, box in marks.items() if box is None]
    if missing:
        raise RuntimeError(f"poppler did not report the marks {missing}")

    bars = []
    for name, share in MARKS:
        x0, y0, x1, y1, _ = marks[name]
        width = (x1 - x0) * share
        print(f"        {name}: box {x1 - x0:.2f}pt wide, bar {width:.2f}pt ({share:.0%})")
        bars.append(
            {
                "x": x0 * CM_PER_PT,
                "y": (y0 - 1) * CM_PER_PT,
                "w": width * CM_PER_PT,
                "h": (y1 - y0 + 2) * CM_PER_PT,
            }
        )
    return bars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-edge-"))
    tmp.mkdir(parents=True, exist_ok=True)

    print("pass 1: exporting the marks alone, to measure each one")
    clean = export(fodt([]), tmp, "pass1-marks")
    bars = bars_over(clean)

    print("pass 2: exporting with the four partial bars")
    final = export(fodt(bars), tmp, "pass2-edge")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
