#!/usr/bin/env python3
"""Build the formatted-values specimen, in both families.

A number in a spreadsheet is stored one way and shown another, and the gap
between them is wider than it looks. A date is stored as `45366`. A reserve
price is stored as `240000` and shown as `240 000,00 zl`. Neither of those
stored values is what the person who hid the row was looking at, and a report
that quotes them has told its reader something they cannot match against the
document.

The two families disagree about how much work that costs:

    ODF     `<table:table-cell office:value="240000"><text:p>240 000,00 zl`
            - the formatted text is in the cell, so there is nothing to do
    OOXML   `<c r="B2" s="1"><v>240000</v>` and a style index, resolved
            through cellXfs -> numFmtId -> formatCode

So the OOXML reader has to resolve the format, and then decide how far to go
with it. It goes exactly as far as it can be exact:

- **A date is rendered.** `45366` is arithmetic, not content, and a hidden
  column of dates reads as gibberish without this. The conversion is exact:
  serial days from 1899-12-30, which is what both producers use.
- **Everything else keeps its stored number**, and the format is named in a
  note. Rendering `#,###.00" zl"` means writing a number formatter, and one
  that is nearly right quotes a figure that is nearly right - which is worse
  in a forensic report than quoting a figure that is exactly the file's.

The hidden row carries both cases so one specimen settles both.

Usage:
    python3 build_calc_formatted_values.py OUTPUT.xlsx OUTPUT.ods [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DECIDED = "2024-03-15"
RESERVE = "240000"
SHOWN_RESERVE = "240 000,00 zl"

FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:automatic-styles>
  <number:date-style style:name="iso">
   <number:year number:style="long"/><number:text>-</number:text>
   <number:month number:style="long"/><number:text>-</number:text>
   <number:day number:style="long"/>
  </number:date-style>
  <style:style style:name="dated" style:family="table-cell" style:data-style-name="iso"/>
  <number:currency-style style:name="zloty">
   <number:number number:decimal-places="2" number:grouping="true"/>
   <number:text> zl</number:text>
  </number:currency-style>
  <style:style style:name="money" style:family="table-cell" style:data-style-name="zloty"/>
 </office:automatic-styles>
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Timetable">
    <table:table-column table:number-columns-repeated="3"/>
    <table:table-row>
     <table:table-cell office:value-type="string"><text:p>Stage</text:p></table:table-cell>
     <table:table-cell office:value-type="string"><text:p>Date</text:p></table:table-cell>
     <table:table-cell office:value-type="string"><text:p>Reserve</text:p></table:table-cell>
    </table:table-row>
    <table:table-row>
     <table:table-cell office:value-type="string"><text:p>Bids opened</text:p></table:table-cell>
     <table:table-cell table:style-name="dated" office:value-type="date"
      office:date-value="2024-04-02"><text:p>2024-04-02</text:p></table:table-cell>
     <table:table-cell office:value-type="string"><text:p>-</text:p></table:table-cell>
    </table:table-row>
    <table:table-row table:visibility="collapse">
     <table:table-cell office:value-type="string"><text:p>Decision taken</text:p></table:table-cell>
     <table:table-cell table:style-name="dated" office:value-type="date"
      office:date-value="{DECIDED}"><text:p>{DECIDED}</text:p></table:table-cell>
     <table:table-cell table:style-name="money" office:value-type="float"
      office:value="{RESERVE}"><text:p>{SHOWN_RESERVE}</text:p></table:table-cell>
    </table:table-row>
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(xlsx: Path, ods: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-fmt-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "timetable.fods"
    source.write_text(FODS, encoding="utf-8")

    for target, fmt in ((xlsx, "xlsx"), (ods, "ods")):
        subprocess.run(
            ["soffice", "--headless", "--convert-to", fmt, str(source), "--outdir", str(scratch)],
            check=True,
            capture_output=True,
        )
        produced = scratch / f"timetable.{fmt}"
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
