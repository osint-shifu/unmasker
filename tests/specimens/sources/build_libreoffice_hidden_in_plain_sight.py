#!/usr/bin/env python3
"""Build the specimen for text that is present, painted, and still unreadable.

Three ways of hiding text that leave it fully in the content stream, none of
which involves drawing anything over it:

  white on paper      the glyphs are painted, in the colour of the page
  matching a fill     the glyphs are painted, in the colour of the box behind
  outside the crop    the glyphs are painted where no viewer shows them

LibreOffice writes the page, as it does for every specimen here. The third case
needs a second step, and finding that out cost a detour worth recording:
**LibreOffice will not emit content that lies outside the page at all.** A
frame placed at -9.5cm is clamped back onto the paper; one placed at 24cm or
30cm is dropped from the output entirely. There is no way to make it produce
text beyond the media box.

So the third line is produced the way it is produced in the wild instead: the
text is laid out near the bottom of the page, and then the **CropBox is set
smaller than the MediaBox**, which every viewer obeys and no parser does. That
is a real technique rather than a contrivance - it is how content survives in
files that were "cropped" rather than edited - and pypdf applies it, which is
an ordinary thing for a PDF tool to do.

Poppler confirms it independently: `pdfinfo` reports the cropped page size while
`pdftotext` still extracts the line.

Everything in the document is invented.

Usage:
    python3 build_libreoffice_hidden_in_plain_sight.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE_W_CM = 21.0
PAGE_H_CM = 29.7

WHITE_ON_PAPER = "Nothing is drawn over this line; it is simply white."
ON_A_BOX = "This line is the colour of the box it sits on."
OFF_THE_CROP = "This line lies below the crop box and no viewer will show it."
VISIBLE = "This line is ordinary black text and must not be reported."

BOX_COLOUR = "#1a3a5f"

STYLES = f"""
  <style:style style:name="Standard" style:family="paragraph">
   <style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt"/>
  </style:style>
  <style:style style:name="Head" style:family="paragraph" style:parent-style-name="Standard">
   <style:paragraph-properties fo:margin-bottom="0.5cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Body" style:family="paragraph" style:parent-style-name="Standard">
   <style:paragraph-properties fo:margin-bottom="0.35cm"/>
  </style:style>
  <style:style style:name="White" style:family="text">
   <style:text-properties fo:color="#ffffff"/>
  </style:style>
  <style:style style:name="OnBox" style:family="text">
   <style:text-properties fo:color="{BOX_COLOUR}"/>
  </style:style>
  <style:style style:name="Box" style:family="graphic">
   <style:graphic-properties draw:fill="solid" draw:fill-color="{BOX_COLOUR}"
    draw:stroke="none" style:run-through="background" style:wrap="run-through"
    style:vertical-pos="from-top" style:vertical-rel="page"
    style:horizontal-pos="from-left" style:horizontal-rel="page"/>
  </style:style>
  <style:style style:name="Offstage" style:family="graphic">
   <style:graphic-properties draw:fill="none" draw:stroke="none"
    style:run-through="foreground" style:wrap="run-through"
    fo:padding="0cm" fo:border="none"
    style:vertical-pos="from-top" style:vertical-rel="page"
    style:horizontal-pos="from-left" style:horizontal-rel="page"/>
  </style:style>
"""


def fodt(box: dict | None) -> str:
    """`box` is the rectangle to draw behind the second line, once measured.

    `style:run-through="background"` puts it *behind* the text, which is the
    whole point: this specimen hides nothing by covering it.
    """
    shapes = ""
    if box:
        shapes += (
            f'<draw:custom-shape text:anchor-type="page" text:anchor-page-number="1"'
            f' draw:style-name="Box" draw:z-index="0"'
            f' svg:x="{box["x"]:.3f}cm" svg:y="{box["y"]:.3f}cm"'
            f' svg:width="{box["w"]:.3f}cm" svg:height="{box["h"]:.3f}cm">'
            f'<draw:enhanced-geometry draw:type="rectangle"/>'
            f"</draw:custom-shape>"
        )

    # Near the bottom of the paper, where the crop applied afterwards will
    # leave it. Placing it outside the page instead does not work: LibreOffice
    # drops such content rather than emitting it.
    offstage = (
        '<draw:frame text:anchor-type="page" text:anchor-page-number="1"'
        ' draw:style-name="Offstage" draw:z-index="1"'
        ' svg:x="2.5cm" svg:y="27.4cm" svg:width="14cm" svg:height="1cm">'
        f"<draw:text-box><text:p>{OFF_THE_CROP}</text:p></draw:text-box>"
        "</draw:frame>"
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
{STYLES}
  <style:page-layout style:name="PL">
   <style:page-layout-properties fo:page-width="{PAGE_W_CM}cm"
    fo:page-height="{PAGE_H_CM}cm" style:print-orientation="portrait"
    fo:margin-top="2.5cm" fo:margin-bottom="2cm"
    fo:margin-left="2.5cm" fo:margin-right="2.5cm"/>
  </style:page-layout>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="PL"/>
 </office:master-styles>
 <office:body><office:text>
  <text:p text:style-name="Head">{shapes}{offstage}HIDDEN IN PLAIN SIGHT - SYNTHETIC</text:p>
  <text:p text:style-name="Body">{VISIBLE}</text:p>
  <text:p text:style-name="Body"><text:span
   text:style-name="White">{WHITE_ON_PAPER}</text:span></text:p>
  <text:p text:style-name="Body"><text:span
   text:style-name="OnBox">{ON_A_BOX}</text:span></text:p>
  <text:p text:style-name="Body">Every line above is in the file. Two of them are
   painted in a colour that hides them, and a fourth lies below the crop box.</text:p>
 </office:text></office:body>
</office:document>
"""


# Where the CropBox's bottom edge goes, in points from the bottom of the page.
# The offstage frame sits at 27.4cm from the top, which is roughly y=45-65pt,
# so 100 leaves it clear of the crop by a comfortable margin.
CROP_BOTTOM_PT = 100.0


def crop(source: Path, target: Path, bottom_pt: float) -> Path:
    """Raise the CropBox above the last line, leaving it in the file.

    A CropBox smaller than the MediaBox is the ordinary way a PDF is trimmed,
    and it removes nothing: every viewer honours it and every parser reads
    straight past it.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        media = page.mediabox
        page.cropbox = page.mediabox.__class__((media.left, bottom_pt, media.right, media.top))
        writer.add_page(page)
    with target.open("wb") as handle:
        writer.write(handle)
    return target


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


def box_for(pdf: Path) -> dict:
    """The rectangle to draw behind the coloured line, from poppler's boxes.

    Poppler rather than this project's own interpreter, for the same reason the
    partial-bars specimen uses it: a fixture measured with the tool under test
    proves only that the tool agrees with itself.
    """
    import html
    import re

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
        (float(m[1]), float(m[2]), float(m[3]), float(m[4]), html.unescape(m[5]))
        for m in re.finditer(pattern, out)
    ]
    pieces = ON_A_BOX.split()
    for start in range(len(words) - len(pieces) + 1):
        window = words[start : start + len(pieces)]
        if [w[4] for w in window] == pieces:
            cm = 2.54 / 72.0
            x0 = min(w[0] for w in window) - 4
            y0 = min(w[1] for w in window) - 3
            x1 = max(w[2] for w in window) + 4
            y1 = max(w[3] for w in window) + 3
            return {"x": x0 * cm, "y": y0 * cm, "w": (x1 - x0) * cm, "h": (y1 - y0) * cm}
    raise RuntimeError("poppler did not report the words of the coloured line")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-plain-"))
    tmp.mkdir(parents=True, exist_ok=True)

    print("pass 1: exporting without the box, to find where the line lands")
    first = export(fodt(None), tmp, "pass1-no-box")
    box = box_for(first)
    print(f"        box at {box['x']:.2f},{box['y']:.2f}cm {box['w']:.2f}x{box['h']:.2f}cm")

    print("pass 2: exporting with the box behind the coloured line")
    final = export(fodt(box), tmp, "pass2-final")

    print("pass 3: cropping the page so the last line falls outside it")
    cropped = crop(final, tmp / "pass3-cropped.pdf", bottom_pt=CROP_BOTTOM_PT)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cropped, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
