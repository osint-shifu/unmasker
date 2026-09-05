#!/usr/bin/env python3
"""Build the Word 97 specimen whose text is not all on the page.

A .doc keeps the text of a tracked deletion **in the piece table, beside the
text that is on the page**. So does text a run marks hidden. Neither is drawn
and both are read by anything that walks the piece table, which means a reader
that stops at the piece table reports a deleted sentence as though somebody
could see it - and reports Word's hidden text as ordinary prose, which is the
exact opposite of what this tool is for.

Which characters those are is in a different structure again: a `Chpx`, in a
512-byte page reached through `PlcfBteChpx`. Nothing about the text says it.

Measured on the file this script writes:

    on the page      Award notice. / added later. / Visible tail ... end.
    in the file too  a deleted sentence, an insertion, and a hidden run

Every sprm this exercises was read out of these bytes before the reader existed,
and one of them corrected a wrong memory: `0x0800` is the **delete** mark and
`0x0801` the insert, not the other way round. `0x083c` is the hidden attribute.

`SttbfRMark`, which holds the names, is an extended string table with a
`0xFFFF` header - the opposite shape from `GrpXstAtnOwners` two structures away
in the same stream, which is a bare run of counted strings with no header at
all. Two string tables, two layouts, one file.

Everything in the text and the metadata is invented.

Usage:

    python3 tests/specimens/sources/build_legacy_word_marks.py tests/specimens/doc
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

FODT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta>
  <dc:creator>Marek Zapasowy-Przyklad</dc:creator>
  <dc:title>Award notice</dc:title>
 </office:meta>
 <office:automatic-styles>
  <style:style style:name="T1" style:family="text">
   <style:text-properties text:display="none"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:tracked-changes>
   <text:changed-region text:id="ct1"><text:deletion>
    <office:change-info><dc:creator>Halina Probna-Test</dc:creator
     ><dc:date>2019-04-02T11:14:00</dc:date></office:change-info>
    <text:p>The second bidder was disqualified for a late submission.</text:p>
   </text:deletion></text:changed-region>
   <text:changed-region text:id="ct2"><text:insertion>
    <office:change-info><dc:creator>Marek Zapasowy-Przyklad</dc:creator
     ><dc:date>2019-04-03T09:00:00</dc:date></office:change-info>
   </text:insertion></text:changed-region>
  </text:tracked-changes>
  <text:p>Award notice.</text:p>
  <text:p><text:change text:change-id="ct1"/><text:change-start
   text:change-id="ct2"/>Both bids were compliant.<text:change-end
   text:change-id="ct2"/></text:p>
  <text:p>Panel decision <text:span text:style-name="T1"
   >- reserve bidder is Wykonawca B -</text:span> is final.</text:p>
 </office:text></office:body>
</office:document>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-marks-"))

    source = work / "marks.fodt"
    source.write_text(FODT, encoding="utf-8")
    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            "--infilter=OpenDocument Text Flat XML",
            "--convert-to", "doc", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )

    data = (work / "marks.doc").read_bytes()
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise RuntimeError("LibreOffice did not write a compound file")

    target = out / "libreoffice-writer-word97-marks.doc"
    target.write_bytes(data)
    print(f"{target}  {len(data)} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/doc"))
