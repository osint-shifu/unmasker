#!/usr/bin/env python3
"""Build the clipped-overflow specimen.

A cell boundary and a redaction by clipping are **the same mechanism**. Text is
drawn, a clipping path is in force, and part of the text falls outside it. One
of those is somebody typing more than fits in a column; the other is somebody
hiding a sentence. The file says nothing about which.

This specimen is the innocent one, and it exists because the tool had no way to
say so. `off-page-text` reported the clipped tail of an overflowing cell in
exactly the same words, and with exactly the same evidence class, as a
paragraph placed outside the crop box - so a spreadsheet exported to PDF could
produce a screenful of findings that were all somebody's column being too
narrow, and a reader who scrolled past them would scroll past a real one.

What the tool can say is which of the two the *rest of the line* supports. Here
every clipped run has visible text beside it on the same line, which is what an
overflow looks like and is not what a redaction looks like. That is a weaker
claim, so it is reported as `circumstantial` rather than suppressed - a
redaction that clips only the second half of a line looks exactly like this
too, and deleting the finding would be deciding for the reader.

The control for the other half is
`libreoffice-writer-hidden-in-plain-sight.pdf`, whose off-page text has no
visible remainder anywhere and stays `direct`.

Usage:
    python3 build_clipped_overflow.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Long enough to overflow a narrow column, with a neighbour occupied so
# LibreOffice clips rather than letting it run on.
ROWS = [
    ("Case", "Owner"),
    ("KZ-2024-0031 opened after the deadline and was admitted anyway", "Probna"),
    ("KZ-2024-0044 withdrawn before the panel met, no reason recorded", "Przyklad"),
]

FODS = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:automatic-styles>
  <style:style style:name="narrow" style:family="table-column">
   <style:table-column-properties style:column-width="3cm"/>
  </style:style>
 </office:automatic-styles>
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Queue">
    <table:table-column table:style-name="narrow"/>
    <table:table-column/>
    {"".join(
        "<table:table-row>"
        + "".join(
            '<table:table-cell office:value-type="string">'
            f"<text:p>{value}</text:p></table:table-cell>"
            for value in row
        )
        + "</table:table-row>"
        for row in ROWS
    )}
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document>
"""


def build(target: Path, workdir: Path | None) -> None:
    scratch = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="unmasker-clip-"))
    scratch.mkdir(parents=True, exist_ok=True)

    source = scratch / "queue.fods"
    source.write_text(FODS, encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", str(source), "--outdir", str(scratch)],
        check=True,
        capture_output=True,
    )
    produced = scratch / "queue.pdf"
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
