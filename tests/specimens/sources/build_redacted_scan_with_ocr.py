#!/usr/bin/env python3
"""Build the redacted scan whose OCR layer was made before the redaction.

A "searchable scan" is a picture of a page with a text layer underneath it,
drawn in render mode 3 so that nothing of it appears on screen. The layer
exists so the document can be searched and copied from, and every OCR pipeline
in the world produces one.

The failure this specimen carries is the order of operations. The scan is
OCR'd, *then* the picture is redacted, and the text layer is never rebuilt. The
black box is painted on the image; the words are still underneath it, invisible
and complete. Nobody looking at the page can tell, because the layer is
invisible by design and there is no visual difference between a scan with an
accurate text layer and a scan with a stale one.

Four producers, none of them this project:

    LibreOffice   writes the page
    Ghostscript   rasterises it, which is what a scanner would have produced
    tesseract     reads the picture and writes the invisible text layer
    ImageMagick   paints the black box on the picture
    pypdf         lays the redacted picture over the original

The box is placed on `pdftotext -bbox` measurements, as every other specimen's
geometry is, so where it lands was not computed by the code that will read it.

Everything is invented.

Usage:
    python3 build_redacted_scan_with_ocr.py OUTPUT.pdf [--workdir DIR]
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

DPI = 200
SECRET = ["250,000", "EUR"]

FODT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="Line" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.4cm"/>
   <style:text-properties fo:font-size="14pt"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:p text:style-name="Line">SETTLEMENT MEMORANDUM - SYNTHETIC</text:p>
  <text:p text:style-name="Line">Agreed figure: 250,000 EUR</text:p>
  <text:p text:style-name="Line">Signed on 17 April 2024 by both parties.</text:p>
 </office:text></office:body>
</office:document>
"""


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, timeout=600)


def box_of(pdf: Path, pieces: list[str]) -> tuple[float, float, float, float]:
    """Where poppler puts these consecutive words, in points from the top-left."""
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
    chosen = [w for w in words if w[4] in pieces]
    if len(chosen) != len(pieces):
        raise RuntimeError(f"poppler did not report {pieces}")
    return (
        min(w[0] for w in chosen) - 3,
        min(w[1] for w in chosen) - 2,
        max(w[2] for w in chosen) + 3,
        max(w[3] for w in chosen) + 2,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-scan-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "memorandum.fodt"
    src.write_text(FODT, encoding="utf-8")

    print("LibreOffice: writing the page")
    run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp / 'loprofile'}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp),
            str(src),
        ]
    )
    original = tmp / "memorandum.pdf"
    if not original.exists():
        raise RuntimeError("LibreOffice produced no PDF")

    print(f"Ghostscript: rasterising at {DPI} dpi, as a scanner would")
    scan = tmp / "scan.png"
    run(
        [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=png16m",
            f"-r{DPI}",
            f"-sOutputFile={scan}",
            str(original),
        ]
    )

    print("tesseract: reading the picture and writing the invisible text layer")
    run(["tesseract", str(scan), str(tmp / "searchable"), "pdf"])
    searchable = tmp / "searchable.pdf"
    if not searchable.exists():
        raise RuntimeError("tesseract produced no PDF")

    x0, y0, x1, y1 = box_of(original, SECRET)
    scale = DPI / 72.0
    left, top, right, bottom = (round(v * scale) for v in (x0, y0, x1, y1))
    print(f"poppler: the figure is at {left},{top} to {right},{bottom} in the picture")

    print("ImageMagick: painting the box on the picture, after the OCR")
    redacted_png = tmp / "scan-redacted.png"
    run(
        [
            "convert",
            str(scan),
            "-fill",
            "black",
            "-draw",
            f"rectangle {left},{top} {right},{bottom}",
            str(redacted_png),
        ]
    )
    redacted_pdf = tmp / "scan-redacted.pdf"
    run(["convert", str(redacted_png), str(redacted_pdf)])

    print("pypdf: laying the redacted picture over the original")
    from pypdf import PdfReader, PdfWriter

    page = PdfReader(str(searchable)).pages[0]
    page.merge_page(PdfReader(str(redacted_pdf)).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    with (tmp / "final.pdf").open("wb") as handle:
        writer.write(handle)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmp / "final.pdf", args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
