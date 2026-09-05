#!/usr/bin/env python3
"""Build the presentation specimen, in both families.

A deck hides two things no other container has. A **slide marked hidden** is
skipped when the deck is shown and travels with the file exactly as authored;
and a **speaker note** was never on the screen at all, which is precisely why
people write candid things in them.

Both are the same statement this tool makes everywhere: in the file, not on the
thing anybody looked at.

This specimen was blocked for most of the project's life. `libreoffice-impress`
was not installed, and `CONTRIBUTING.md` is explicit that a detector proved
only against a hand-built fixture is the shape of the bug that started this
project - so rather than write the reader against the specification, both
formats were refused outright and the reason was written down. Installing
Impress unblocked it.

Two producer facts, measured against what came back rather than read out of a
specification:

- **ODF puts a slide's visibility behind a named style**, exactly as it does a
  spreadsheet's hidden sheet: the page carries `draw:style-name="dp3"` and the
  style, elsewhere in the file, says `presentation:visibility="hidden"`. A
  reader looking for an attribute on the page finds nothing.
- **OOXML writes `show="0"` and omits it entirely when the slide is shown.**
  That is the opposite of what the same producer does for a hidden *row* in a
  spreadsheet, where it writes `hidden="false"` out loud on every row - so a
  reader carrying that habit across would find no hidden slides at all.

The deck is a board review because that is where the two failures cost
something: the slide that was cut before the meeting, and the line the speaker
was told not to say. Everything is invented.

Usage:
    python3 build_impress_deck.py OUTPUT.odp OUTPUT.pptx [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SHOWN = "Q3 board review"
SHOWN_BODY = "Revenue held. Two contracts renewed on the same terms."
NOTE = "Do not give the headcount number if anyone asks. Legal has not signed it off."

CUT_TITLE = "Redundancies - draft"
CUT_BODY = "41 roles, mostly Warsaw. Announce after the results, not before."

SECOND = "Outlook"
SECOND_BODY = "Guidance unchanged."


def _frame(text: str, y: str, size: str = "20pt") -> str:
    return (
        f'<draw:frame svg:width="22cm" svg:height="3cm" svg:x="2cm" svg:y="{y}" '
        f'draw:style-name="gr1">'
        f"<draw:text-box><text:p>{text}</text:p></draw:text-box></draw:frame>"
    )


def _notes(text: str) -> str:
    return (
        "<presentation:notes>"
        '<draw:frame svg:width="18cm" svg:height="6cm" svg:x="2cm" svg:y="12cm">'
        f"<draw:text-box><text:p>{text}</text:p></draw:text-box></draw:frame>"
        "</presentation:notes>"
    )


FODP = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.presentation">
 <office:meta><meta:initial-creator>Halina Probna-Test</meta:initial-creator></office:meta>
 <office:automatic-styles>
  <style:page-layout style:name="PM1">
   <style:page-layout-properties fo:page-width="28cm" fo:page-height="15.75cm"/>
  </style:page-layout>
  <style:style style:name="gr1" style:family="graphic">
   <style:text-properties fo:font-size="20pt"/>
  </style:style>
  <style:style style:name="dpvis" style:family="drawing-page">
   <style:drawing-page-properties presentation:visibility="visible"/>
  </style:style>
  <style:style style:name="dphid" style:family="drawing-page">
   <style:drawing-page-properties presentation:visibility="hidden"/>
  </style:style>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Default" style:page-layout-name="PM1"/>
 </office:master-styles>
 <office:body>
  <office:presentation>
   <draw:page draw:name="Opening" draw:master-page-name="Default" draw:style-name="dpvis">
    {_frame(SHOWN, "2cm")}
    {_frame(SHOWN_BODY, "6cm")}
    {_notes(NOTE)}
   </draw:page>
   <draw:page draw:name="Cut" draw:master-page-name="Default" draw:style-name="dphid">
    {_frame(CUT_TITLE, "2cm")}
    {_frame(CUT_BODY, "6cm")}
   </draw:page>
   <draw:page draw:name="Outlook" draw:master-page-name="Default" draw:style-name="dpvis">
    {_frame(SECOND, "2cm")}
    {_frame(SECOND_BODY, "6cm")}
   </draw:page>
  </office:presentation>
 </office:body>
</office:document>
"""


def build(odp: Path, pptx: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-deck-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "review.fodp"
    source.write_text(FODP, encoding="utf-8")

    for target, fmt in ((odp, "odp"), (pptx, "pptx")):
        subprocess.run(
            ["soffice", "--headless", "--convert-to", fmt, str(source), "--outdir", str(scratch)],
            check=True,
            capture_output=True,
        )
        produced = scratch / f"review.{fmt}"
        if not produced.exists():
            raise SystemExit(f"soffice produced no {fmt} - is libreoffice-impress installed?")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced, target)
        print(f"wrote {target} ({target.stat().st_size} bytes)")

    if workdir is None:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("odp", type=Path)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    build(args.odp, args.pptx, args.workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
