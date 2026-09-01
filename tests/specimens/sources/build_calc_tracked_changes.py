#!/usr/bin/env python3
"""Build the spreadsheet tracked-changes specimen, in both families.

Change tracking in a spreadsheet keeps the **previous value of a cell** inside
the file. A bid edited from 240 000 down to 198 000 still holds the 240 000,
beside the name of whoever changed it and the minute they did, and the person
looking at the sheet sees one number. It is `w:delText` again, arriving through
a container that has cells instead of paragraphs - and unlike a Word deletion,
this one has a *current* value to sit beside, so the report can fill both of
its columns with real text rather than leaving one empty.

Four producer facts were measured before this was written, and three of them
would have been invisible in a fixture built from the specification:

- **A numeric previous value keeps only the attribute.** LibreOffice writes
  `<table:change-track-table-cell office:value="240000"/>` and *strips the
  `<text:p>`* the source had. A reader that looks for the paragraph finds
  nothing.
- **A string previous value keeps only the paragraph.** The same element,
  written the other way round: `<text:p>rejected on price</text:p>` and no
  `office:value` at all. Either half alone reads half the changes.
- **A tracked row deletion carries no content.** LibreOffice writes the
  author, the date and the position, and no cells. So it is remarked on and
  counted, and it is not a finding: a finding that quotes nothing teaches a
  reader to skip findings.
- **`<nc>` holds the old value.** The .xlsx revision log writes the "new cell"
  element with the *previous* contents, in both the numeric and the string
  case. Believing it would report a cell that changed from 240000 to 240000, so
  the current value is read out of the sheet in both families - which is where
  a person would look anyway.
- **`xl/revisions/` is one log part per editing session.** This file has
  three, reached through relationships from `revisionHeaders.xml`, and the
  author and date are on the *header* rather than on the change. Reading
  `revisionLog1.xml` and stopping reports one change out of three and gives no
  sign of having stopped - which is exactly what a first look at this file
  suggested was the export losing them. It was not.

Everything is invented. The sheet is a bid comparison because that is where an
edited figure costs something and where change tracking is routinely left on
by accident.

Usage:
    python3 build_calc_tracked_changes.py OUTPUT.ods OUTPUT.xlsx [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EDITOR = "Halina Probna-Test"
SECOND = "Piotr Przyklad"

WAS_OFFER = "240000"
NOW_OFFER = "198000"
WAS_NOTE = "rejected on price"
NOW_NOTE = "shortlisted"

ROWS = [
    ("Party", "Offer", "Note"),
    ("Kowalski i Wspolnicy sp. z o.o.", NOW_OFFER, NOW_NOTE),
    ("Nowak Systemy SA", "231000", "held"),
]

NUMERIC = {1}


def _cell(index: int, text: str) -> str:
    if index in NUMERIC and text.isdigit():
        attrs = f'office:value-type="float" office:value="{text}"'
    else:
        attrs = 'office:value-type="string"'
    return f"<table:table-cell {attrs}><text:p>{text}</text:p></table:table-cell>"


def _rows() -> str:
    return "".join(
        "<table:table-row>"
        + "".join(_cell(i, v) for i, v in enumerate(values))
        + "</table:table-row>"
        for values in ROWS
    )


def _change(identifier: str, who: str, when: str, column: int, row: int, previous: str) -> str:
    """One cell-content change, with its previous value written both ways.

    The source states the value *and* the paragraph; LibreOffice keeps whichever
    one suits the type and drops the other, which is the point of measuring
    rather than assuming.
    """
    if previous.isdigit():
        cell = (
            f'<table:change-track-table-cell office:value-type="float" '
            f'office:value="{previous}"><text:p>{previous}</text:p>'
            "</table:change-track-table-cell>"
        )
    else:
        cell = (
            '<table:change-track-table-cell office:value-type="string">'
            f"<text:p>{previous}</text:p></table:change-track-table-cell>"
        )
    return (
        f'<table:cell-content-change table:id="{identifier}">'
        f"<office:change-info><dc:creator>{who}</dc:creator>"
        f"<dc:date>{when}</dc:date></office:change-info>"
        f'<table:cell-address table:column="{column}" table:row="{row}" table:table="0"/>'
        f'<table:previous table:id="{identifier}">{cell}</table:previous>'
        "</table:cell-content-change>"
    )


TRACKED = (
    '<table:tracked-changes table:track-changes="true">'
    + _change("ct1", EDITOR, "2024-06-12T09:14:00", 1, 1, WAS_OFFER)
    + _change("ct2", SECOND, "2024-06-12T16:40:00", 2, 1, WAS_NOTE)
    + '<table:deletion table:id="ct3" table:type="row" table:position="3">'
    + f"<office:change-info><dc:creator>{EDITOR}</dc:creator>"
    + "<dc:date>2024-06-13T08:02:00</dc:date></office:change-info>"
    + "</table:deletion>"
    + "</table:tracked-changes>"
)

FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:meta><meta:initial-creator>{EDITOR}</meta:initial-creator></office:meta>
 <office:body>
  <office:spreadsheet>
   {TRACKED}
   <table:table table:name="Bids">
    <table:table-column table:number-columns-repeated="3"/>
    {_rows()}
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(ods: Path, xlsx: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-track-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "bids.fods"
    source.write_text(FODS, encoding="utf-8")

    for target, fmt in ((ods, "ods"), (xlsx, "xlsx")):
        subprocess.run(
            ["soffice", "--headless", "--convert-to", fmt, str(source), "--outdir", str(scratch)],
            check=True,
            capture_output=True,
        )
        produced = scratch / f"bids.{fmt}"
        if not produced.exists():
            raise SystemExit(f"soffice produced no {fmt}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced, target)
        print(f"wrote {target} ({target.stat().st_size} bytes)")

    if workdir is None:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ods", type=Path)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    build(args.ods, args.xlsx, args.workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
