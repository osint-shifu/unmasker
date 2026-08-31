#!/usr/bin/env python3
"""Build the LibreOffice Writer failed-redaction specimen.

The point of this script is that *LibreOffice* writes the PDF. Nothing here
emits a `re` or an `f` operator by hand. We write a Flat ODF document - the
same XML LibreOffice itself saves - and let `soffice` export it, so the content
stream, the graphics state, the subset fonts and the shape geometry are all
LibreOffice's own output. A fixture assembled from the PDF specification would
prove nothing about a file a real producer wrote.

It runs in two passes, because the whole value of the specimen is that the
rectangle really does cover the text:

  pass 1   export the text alone, then measure where each line actually
           landed, using the same pypdf text visitor the tool will use
  pass 2   re-export with black rectangles placed on the measured positions

Guessing the coordinates would produce a specimen whose rectangle *almost*
covers its text, and a detector tuned against that is worse than no detector.

Everything in the document is invented. Names, addresses, the case number and
the phone number are fictional; the e-mail domain is `example.org`, which RFC
2606 reserves for exactly this.

Usage:
    python3 build_libreoffice_writer.py OUTPUT.pdf [--workdir DIR] [--keep]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CM_PER_PT = 2.54 / 72.0

# A4 portrait, the LibreOffice default on this machine.
PAGE_W_CM = 21.0
PAGE_H_CM = 29.7
PAGE_H_PT = PAGE_H_CM / CM_PER_PT

# The document body. Each entry is (label, value, redact).
#
# A real redactor covers the value and leaves the label legible - that is what
# makes these documents readable at all after release, and it is why the label
# is a reliable clue to what the bar is hiding. We reproduce that habit.
FIELDS = [
    ("Name", "Wanda Testowa-Przyklad", True),
    ("Email", "w.testowa@example.org", True),
    ("Telephone", "+48 601 000 000", True),
    ("Address", "ul. Przykladowa 12/3, 00-001 Warszawa", True),
    ("Filed", "17 April 2024", False),
    ("Registry", "SYN-2024-0417", False),
]

HEADING = "SYNTHETIC DISCLOSURE - NOT A REAL CASE"
INTRO = (
    "The identifying particulars of the complainant are set out below. "
    "They have been redacted prior to release."
)
CLOSING = (
    "This file is a test specimen for the unmasker project. Every particular in it is invented."
)

# Liberation Serif and Liberation Mono ship with LibreOffice, so the layout is
# reproducible on any machine that can run the builder at all.
STYLES = """
  <style:style style:name="Standard" style:family="paragraph">
   <style:text-properties style:font-name="Liberation Serif" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="Head" style:family="paragraph" style:parent-style-name="Standard">
   <style:paragraph-properties fo:margin-bottom="0.6cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Body" style:family="paragraph" style:parent-style-name="Standard">
   <style:paragraph-properties fo:margin-bottom="0.4cm"/>
  </style:style>
  <style:style style:name="Field" style:family="paragraph" style:parent-style-name="Standard">
   <style:paragraph-properties fo:margin-bottom="0.25cm"/>
   <style:text-properties style:font-name="Liberation Mono" fo:font-size="11pt"/>
  </style:style>
  <style:style style:name="Bar" style:family="graphic">
   <style:graphic-properties draw:fill="solid" draw:fill-color="#000000"
    draw:stroke="none" draw:opacity="100%"
    style:run-through="foreground" style:wrap="run-through"
    style:vertical-pos="from-top" style:vertical-rel="page"
    style:horizontal-pos="from-left" style:horizontal-rel="page"/>
  </style:style>
"""


def fodt(bars: list[dict] | None = None, remove_text: bool = False) -> str:
    """Return a Flat ODF Writer document, optionally with black bars on top.

    `style:run-through="foreground"` is the line that matters. It puts the
    shape in front of the text instead of behind it, which is precisely the
    real-world failure: the text is never removed, only covered.

    With `remove_text`, the redacted values are replaced by spaces before the
    bars go on. That is a *correct* redaction, and it is here so the specimen
    set can tell the two apart. The values are set in Liberation Mono, where a
    space has the same advance as any other glyph, so the layout does not move
    and the two files differ only in whether the text is still there.
    """
    shapes = ""
    for b in bars or []:
        shapes += (
            f'<draw:custom-shape text:anchor-type="page" text:anchor-page-number="1"'
            f' draw:style-name="Bar" draw:z-index="{b["z"]}"'
            f' svg:x="{b["x"]:.3f}cm" svg:y="{b["y"]:.3f}cm"'
            f' svg:width="{b["w"]:.3f}cm" svg:height="{b["h"]:.3f}cm">'
            f'<draw:enhanced-geometry draw:type="rectangle"/>'
            f"</draw:custom-shape>"
        )

    body = [f'<text:p text:style-name="Head">{shapes}{HEADING}</text:p>']
    body.append(f'<text:p text:style-name="Body">{INTRO}</text:p>')
    for label, value, redact in FIELDS:
        # U+00A0, not a plain space: ODF collapses runs of ordinary spaces
        # unless they are written as <text:s/>, and the columns would move.
        pad = " " * (12 - len(label) - 1)
        shown = " " * len(value) if (remove_text and redact) else value
        body.append(f'<text:p text:style-name="Field">{label}:{pad}{shown}</text:p>')
    body.append('<text:p text:style-name="Body"/>')
    body.append(f'<text:p text:style-name="Body">{CLOSING}</text:p>')

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
  {"".join(body)}
 </office:text></office:body>
</office:document>
"""


def export(fodt_text: str, workdir: Path, stem: str) -> Path:
    """Hand the document to LibreOffice and return the PDF it produced."""
    src = workdir / f"{stem}.fodt"
    src.write_text(fodt_text, encoding="utf-8")
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


def measure(pdf: Path) -> list[tuple[str, float, float, float]]:
    """Return (text, x, baseline_y, font_size) for every fragment on page 1.

    Uses pypdf's `visitor_text` hook, the same one the tool will use, so the
    coordinates the bars are placed on come from the same source of truth the
    detector will later read.
    """
    from pypdf import PdfReader

    found: list[tuple[str, float, float, float]] = []

    def visit(text, cm, tm, font_dict, font_size):  # noqa: ANN001, ARG001
        if text and text.strip():
            found.append((text, tm[4], tm[5], font_size))

    PdfReader(str(pdf)).pages[0].extract_text(visitor_text=visit)
    return found


def bars_for(frags: list[tuple[str, float, float, float]]) -> list[dict]:
    """Place a black bar over each field value that FIELDS marks for redaction.

    The bar is sized from the measured baseline and font size, then widened the
    way a person dragging a mouse widens it - nobody lands on the exact glyph
    extent. Generous coverage is both more realistic and unambiguous evidence
    that an overlap really is an overlap.
    """
    wanted = {v: label for label, v, red in FIELDS if red}
    bars: list[dict] = []

    for text, x, y, size in frags:
        value = next((v for v in wanted if v and v in text), None)
        if value is None:
            continue
        wanted.pop(value)

        size = size or 11.0
        # Where the value starts inside the fragment. The label and its padding
        # sit in the same run, so shift right by their measured share.
        offset = text.index(value)
        char_w = size * 0.60  # Liberation Mono advance width, 0.6 em
        x_pt = x + offset * char_w
        w_pt = len(value) * char_w

        top_pt = y + size * 0.88  # a little above the ascender
        h_pt = size * 1.30  # down past the descender

        bars.append(
            {
                "x": (x_pt - 2.0) * CM_PER_PT,
                "y": (PAGE_H_PT - top_pt) * CM_PER_PT,
                "w": (w_pt + 6.0) * CM_PER_PT,
                "h": h_pt * CM_PER_PT,
                "z": 10 + len(bars),
                "covers": value,
            }
        )

    if wanted:
        raise RuntimeError(f"could not locate these values in the PDF text: {sorted(wanted)}")
    return bars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    ap.add_argument("--keep", action="store_true", help="keep the intermediate files")
    ap.add_argument(
        "--remove-text",
        action="store_true",
        help="build the control instead: bars drawn, text genuinely gone",
    )
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-specimen-"))
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        print("pass 1: exporting the text alone")
        clean = export(fodt(), tmp, "pass1-text-only")
        frags = measure(clean)
        print(f"        {len(frags)} positioned fragments on page 1")

        bars = bars_for(frags)
        for b in bars:
            print(f"        bar over {b['covers']!r} at {b['x']:.2f},{b['y']:.2f}cm")

        what = "bars in place, text removed" if args.remove_text else "the bars in place"
        print(f"pass 2: exporting with {what}")
        covered = export(fodt(bars, remove_text=args.remove_text), tmp, "pass2-redacted")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(covered, args.output)
        print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    finally:
        if not args.keep and args.workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)
        elif args.keep:
            print(f"intermediates kept in {tmp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
