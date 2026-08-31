#!/usr/bin/env python3
"""Build the filtered-rows specimen.

`table:visibility` has three values and only two of them mean the same thing.
`collapse` is a person having hidden the row. `filter` is a filter holding it
back - the rows come back when it is cleared, and whoever is looking at the
screen set it and knows they set it. Both put text in the file that is not on
the screen, so both are reported; they are not the same claim, so they are not
reported the same way.

That distinction is why this file is separate from
`libreoffice-calc-hidden-columns.ods` rather than another row in it. Exporting
that specimen to .xlsx flattens `filter` into `hidden="true"` and writes no
`autoFilter` element at all, so the two families would disagree about one
source document - which is true, and worth stating, but would have cost the
strongest test the other specimen has: that both families report the same
hiding.

Everything is invented. The list is an internal case queue, which is where a
filter is left on by accident and the file is sent out with the queue still in
it.

Usage:
    python3 build_calc_filtered_rows.py OUTPUT.ods [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OPEN_CASES = [
    ("KZ-2024-0031", "open", "Meridian Trust BV"),
    ("KZ-2024-0044", "open", "Testowa Grupa sp. j."),
]
FILTERED = [
    ("KZ-2023-0912", "referred to prosecutor", "Nowak Systemy SA"),
    ("KZ-2023-0948", "referred to prosecutor", "Kowalski i Wspolnicy sp. z o.o."),
]

HEADER = ("Case", "Status", "Party")


def _row(values, visibility: str = "") -> str:
    attribute = f' table:visibility="{visibility}"' if visibility else ""
    cells = "".join(
        f'<table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell>'
        for v in values
    )
    return f"<table:table-row{attribute}>{cells}</table:table-row>"


def _body() -> str:
    rows = [_row(HEADER)]
    rows.append(_row(OPEN_CASES[0]))
    # The filtered pair sits in the middle, so a reader that collapses a run of
    # consecutive rows has a run to collapse and the row numbers stay checkable.
    rows.extend(_row(values, "filter") for values in FILTERED)
    rows.append(_row(OPEN_CASES[1]))
    return "".join(rows)


FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Queue">
    <table:table-column table:number-columns-repeated="3"/>
    {_body()}
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(target: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-filter-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "queue.fods"
    source.write_text(FODS, encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "ods", str(source), "--outdir", str(scratch)],
        check=True,
        capture_output=True,
    )
    produced = scratch / "queue.ods"
    if not produced.exists():
        raise SystemExit("soffice produced no ods")
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
