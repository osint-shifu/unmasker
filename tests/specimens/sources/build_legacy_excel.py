#!/usr/bin/env python3
"""Build the Excel 97 specimen, whose cells this tool still does not read.

It is here to hold a **negative** claim still. A .doc's text is read now; a
.xls's is not, because BIFF is a different format again - a stream of tagged
records rather than a piece table - and none of it is implemented. The remark
that says so used to cover all three compound-file formats at once, and
loosening it to keep covering Word after Word became readable is exactly how a
report ends up claiming a search that never happened.

So this file exists to fail the test if that ever slips: a workbook must go on
saying its text was not read, and must go on giving up the property streams
that say who wrote it.

Everything in the metadata and the cells is invented.

Usage:

    python3 tests/specimens/sources/build_legacy_excel.py tests/specimens/xls
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

FODS = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:meta>
  <dc:creator>Marek Zapasowy-Przyklad</dc:creator>
  <dc:title>Scoring sheet - internal</dc:title>
  <meta:user-defined meta:name="Company">Osint Shifu sp. z o.o.</meta:user-defined>
 </office:meta>
 <office:body><office:spreadsheet>
  <table:table table:name="Scores">
   <table:table-row>
    <table:table-cell office:value-type="string"><text:p>Bidder</text:p></table:table-cell>
    <table:table-cell office:value-type="string"><text:p>Score</text:p></table:table-cell>
   </table:table-row>
   <table:table-row>
    <table:table-cell office:value-type="string"><text:p>Wykonawca A</text:p></table:table-cell>
    <table:table-cell office:value-type="float"
     office:value="84"><text:p>84</text:p></table:table-cell>
   </table:table-row>
  </table:table>
 </office:spreadsheet></office:body>
</office:document>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-xls-"))

    source = work / "scores.fods"
    source.write_text(FODS, encoding="utf-8")
    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            "--convert-to", "xls", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )

    data = (work / "scores.xls").read_bytes()
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise RuntimeError("LibreOffice did not write a compound file")

    target = out / "libreoffice-calc-excel97.xls"
    target.write_bytes(data)
    print(f"{target}  {len(data)} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/xls"))
