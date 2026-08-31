#!/usr/bin/env python3
"""Build the spreadsheet specimen, in both families.

A spreadsheet hides things in a way no other container does. There is no
geometry, no invisible character and no tracked change: a row, a column or a
whole sheet simply carries an attribute saying not to draw it, and every value
in it stays in the file exactly as typed. Someone selects three columns,
right-clicks, chooses Hide, and sends the workbook out believing the numbers
are gone.

This is a tender evaluation because that is where the failure is worth
something. The reserve price is what a bidder must not know, the withdrawn
bidder is who the other bidders must not know about, and the workings sheet is
the arithmetic nobody outside the panel is supposed to see. Every particular is
invented.

The same source is exported twice, for the same reason the metadata pair is:
the two families state hiding *differently*, and a reader tried on one of them
would have a partial idea of what hiding is.

    XLSX    an attribute on the thing itself - `state`, `hidden`
    ODS     `table:visibility` on rows and columns, but for a whole sheet an
            indirection through a named style in `office:automatic-styles`

Two producer facts were measured before this was written, not read out of the
specification:

- **LibreOffice ignores `table:display="false"` on a column style.** The first
  attempt hid a column that way, which is what the ODF specification suggests,
  and the conversion silently dropped it in *both* exports. The form that
  round-trips is `table:visibility="collapse"` on the column itself.
- **LibreOffice writes `hidden="false"` explicitly** on every unhidden row of
  the .xlsx. A reader that tests whether the attribute is present, rather than
  what it says, reports every row in the workbook.

Usage:
    python3 build_calc_hidden_columns.py OUTPUT.xlsx OUTPUT.ods [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EVALUATOR = "Halina Probna-Test"

RESERVE = "Reserve price (EUR)"
WITHDRAWN = "Delta Consulting sp. z o.o."
WITHDRAWN_NOTE = "withdrawn after the deadline - do not list"
COMMENT = "Panel agreed the reserve before the bids were opened. Not for the file we release."
WORKINGS = "Reserve set at 240,000. Kowalski came in 12% under; the others were told nothing."

# One row per bidder. The fourth column is the one that gets hidden, and the
# third bidder is the row that gets hidden - so a reader has to get both axes
# right to report this file correctly.
HEADER = ["Bidder", "Technical", "Price", RESERVE, "Total", "Award"]
ROWS = [
    (["Kowalski i Wspolnicy sp. z o.o.", "78", "62", "211000", "71", "awarded"], False),
    (["Nowak Systemy SA", "65", "71", "238000", "68", "-"], False),
    ([WITHDRAWN, "82", "44", "196000", "63", WITHDRAWN_NOTE], True),
    (["Testowa Grupa sp. j.", "55", "80", "251000", "66", "-"], False),
]

NUMERIC = {1, 2, 3, 4}
HIDDEN_COLUMN = 3  # zero-based: the reserve price
COMMENTED = (0, 5)  # the award cell of the first bidder


def _cell(index: int, text: str, annotation: str = "") -> str:
    if index in NUMERIC and text.lstrip("-").isdigit():
        attrs = f'office:value-type="float" office:value="{text}"'
    else:
        attrs = 'office:value-type="string"'
    return (
        f"<table:table-cell {attrs}>{annotation}"
        f"<text:p>{text}</text:p></table:table-cell>"
    )


def _row(values: list[str], hidden: bool, annotate: int | None = None) -> str:
    visibility = ' table:visibility="collapse"' if hidden else ""
    cells = []
    for index, value in enumerate(values):
        annotation = ""
        if annotate is not None and index == annotate:
            annotation = (
                "<office:annotation>"
                f"<dc:creator>{EVALUATOR}</dc:creator>"
                "<dc:date>2024-06-11T14:05:00</dc:date>"
                f"<text:p>{COMMENT}</text:p>"
                "</office:annotation>"
            )
        cells.append(_cell(index, value, annotation))
    return f"<table:table-row{visibility}>" + "".join(cells) + "</table:table-row>"


def _columns() -> str:
    out = []
    for index in range(len(HEADER)):
        visibility = ' table:visibility="collapse"' if index == HIDDEN_COLUMN else ""
        out.append(f"<table:table-column{visibility}/>")
    return "".join(out)


def _body() -> str:
    rows = [_row(HEADER, False)]
    for index, (values, hidden) in enumerate(ROWS):
        rows.append(_row(values, hidden, annotate=COMMENTED[1] if index == COMMENTED[0] else None))
    return "".join(rows)


FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:meta>
  <meta:initial-creator>{EVALUATOR}</meta:initial-creator>
  <dc:title>Tender evaluation - panel copy</dc:title>
 </office:meta>
 <office:automatic-styles>
  <style:style style:name="hidden-sheet" style:family="table">
   <style:table-properties table:display="false"/>
  </style:style>
 </office:automatic-styles>
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Evaluation">
    {_columns()}
    {_body()}
   </table:table>
   <table:table table:name="Workings" table:style-name="hidden-sheet">
    <table:table-column/>
    <table:table-row>
     <table:table-cell office:value-type="string">
      <text:p>{WORKINGS}</text:p>
     </table:table-cell>
    </table:table-row>
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(xlsx: Path, ods: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-calc-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "evaluation.fods"
    source.write_text(FODS, encoding="utf-8")

    for target, fmt in ((xlsx, "xlsx"), (ods, "ods")):
        subprocess.run(
            # Separate arguments, not `--convert-to=xlsx`: this LibreOffice
            # rejects the joined form and prints its usage instead.
            ["soffice", "--headless", "--convert-to", fmt, str(source), "--outdir", str(scratch)],
            check=True,
            capture_output=True,
        )
        produced = scratch / f"evaluation.{fmt}"
        if not produced.exists():
            raise SystemExit(f"soffice produced no {fmt}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced, target)
        print(f"wrote {target} ({target.stat().st_size} bytes)")

    if workdir is None:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("ods", type=Path)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    build(args.xlsx, args.ods, args.workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
