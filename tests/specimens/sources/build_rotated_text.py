#!/usr/bin/env python3
"""Build the rotated-text specimen.

Every detector that reports a line of text groups the page's glyphs into lines
first, and until this file existed it did that by **the bottom of the glyph
box**. That is exact for horizontal text and wrong for anything else: turn a
line ninety degrees and every glyph in it has a different bottom edge and the
same left edge, so one hidden line becomes one finding per letter.

Measured on this file before the fix: `low-contrast-text` reported **18
findings** for a single rotated line, one for each of `W`, `I`, `T`, `H`, `D`,
`R`... It is the same failure Chrome's one-glyph-per-`Tj` produced on the
covered-text detector, arriving from a completely different direction, and the
grouping rule that fixed the first did not survive the second.

Rotated column headers are ordinary spreadsheet practice - they are how a wide
table fits on a page - so this is not a contrived arrangement. The hidden
header is white on the paper, which is the cheapest way to make a column
disappear without deleting it.

The first column is given an explicit width, and the visible headers are kept
short, for a reason worth writing down. At the default width the bidder names
overflow their cell and LibreOffice **clips** them, and `off-page-text`
correctly reports the clipped letter as a character in the file and not on the
page. That is true, and it is nothing to do with what this file tests - so the
specimen is widened rather than the detector tuned. The observation is recorded
in `tests/specimens/README.md`: a cell boundary clipping one glyph of ordinary
visible text is not concealment, and no rule here separates the two.

Usage:
    python3 build_rotated_text.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HIDDEN_HEADER = "WITHDRAWN 196000"
VISIBLE_HEADERS = ("Technical", "Price")
BODY = [
    ("Kowalski i Wspolnicy sp. z o.o.", "78", "62"),
    ("Nowak Systemy SA", "65", "71"),
]

FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:automatic-styles>
  <style:style style:name="upright" style:family="table-cell">
   <style:table-cell-properties style:rotation-angle="90"/>
   <style:text-properties fo:color="#000000"/>
  </style:style>
  <style:style style:name="upright-white" style:family="table-cell">
   <style:table-cell-properties style:rotation-angle="90"/>
   <style:text-properties fo:color="#ffffff"/>
  </style:style>
  <style:style style:name="flat" style:family="table-cell">
   <style:text-properties fo:color="#000000"/>
  </style:style>
  <style:style style:name="wide" style:family="table-column">
   <style:table-column-properties style:column-width="7cm"/>
  </style:style>
 </office:automatic-styles>
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Summary">
    <table:table-column table:style-name="wide"/>
    <table:table-column table:number-columns-repeated="3"/>
    <table:table-row>
     <table:table-cell office:value-type="string"><text:p>Party</text:p></table:table-cell>
     <table:table-cell table:style-name="upright" office:value-type="string">
      <text:p>{VISIBLE_HEADERS[0]}</text:p></table:table-cell>
     <table:table-cell table:style-name="upright" office:value-type="string">
      <text:p>{VISIBLE_HEADERS[1]}</text:p></table:table-cell>
     <table:table-cell table:style-name="upright-white" office:value-type="string">
      <text:p>{HIDDEN_HEADER}</text:p></table:table-cell>
    </table:table-row>
    {"".join(
        "<table:table-row>"
        + f'<table:table-cell table:style-name="flat" office:value-type="string">'
          f"<text:p>{party}</text:p></table:table-cell>"
        + f'<table:table-cell table:style-name="flat" office:value-type="float" '
          f'office:value="{tech}"><text:p>{tech}</text:p></table:table-cell>'
        + f'<table:table-cell table:style-name="flat" office:value-type="float" '
          f'office:value="{price}"><text:p>{price}</text:p></table:table-cell>'
        + "</table:table-row>"
        for party, tech, price in BODY
    )}
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(target: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-rot-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "summary.fods"
    source.write_text(FODS, encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", str(source), "--outdir", str(scratch)],
        check=True,
        capture_output=True,
    )
    produced = scratch / "summary.pdf"
    if not produced.exists():
        raise SystemExit("soffice produced no pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(produced, target)
    print(f"wrote {target} ({target.stat().st_size} bytes)")

    if workdir is None:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    build(args.output, args.workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
