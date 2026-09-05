#!/usr/bin/env python3
"""Build the embedded-object specimens, in both office families.

A word processor lets you place a spreadsheet inside a document. What the page
shows is a **rendering** of it - LibreOffice writes an EMF picture beside the
object for exactly that purpose - while the package carries the spreadsheet
itself, complete, as a file.

That is a different statement from a PDF attachment and must be reported as a
different one. The object is not hidden: it is on the page. What is on the page
is a picture of it, and the file the picture was made from travels with the
document.

Measured on the files this script writes:

    ODT    Object 1/content.xml          a sub-package, a whole spreadsheet
    DOCX   word/embeddings/oleObject1.xlsx   a whole workbook, ~5 KB
           word/media/image1.emf         the picture the page actually shows

## How they are produced

Flat ODF, converted by LibreOffice. The input filter has to be named: the inner
`office:document` carries the spreadsheet's own mimetype, and left to detect the
type itself LibreOffice reads the whole file as a Calc document and the
conversion fails. The DOCX is that ODT converted again, so both come out of the
producer rather than out of this script.

Everything is invented.

Usage:

    python3 tests/specimens/sources/build_embedded_object.py tests/specimens
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

VISIBLE = "Summary of the award. No figures are disclosed in this paragraph."

FODT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:body><office:text>
  <text:p>{visible}</text:p>
  <text:p>
   <draw:frame draw:name="Workings" svg:width="12cm" svg:height="3cm"
    text:anchor-type="as-char">
    <draw:object>
     <office:document office:mimetype="application/vnd.oasis.opendocument.spreadsheet"
      office:version="1.3">
      <office:body><office:spreadsheet>
       <table:table table:name="Workings">
        <table:table-row>
         <table:table-cell office:value-type="string"><text:p>Reserve</text:p></table:table-cell>
         <table:table-cell office:value-type="float" office:value="240000">
          <text:p>240000</text:p></table:table-cell>
        </table:table-row>
        <table:table-row>
         <table:table-cell office:value-type="string"><text:p>Told early</text:p></table:table-cell>
         <table:table-cell office:value-type="string"><text:p>Kowalski</text:p></table:table-cell>
        </table:table-row>
       </table:table>
      </office:spreadsheet></office:body>
     </office:document>
    </draw:object>
   </draw:frame>
  </text:p>
 </office:text></office:body>
</office:document>
"""


def convert(src: Path, work: Path, outdir: Path, target: str, infilter: str = "") -> Path:
    command = [
        "soffice", "--headless", "--norestore",
        f"-env:UserInstallation=file://{work / 'loprofile'}",
    ]
    if infilter:
        command += [f"--infilter={infilter}"]
    command += ["--convert-to", target, "--outdir", str(outdir), str(src)]
    subprocess.run(command, check=True, capture_output=True, timeout=300)

    produced = outdir / f"{src.stem}.{target.split(':')[0]}"
    if not produced.exists():
        raise RuntimeError(f"LibreOffice produced no {target} for {src}")
    return produced


def main(out: Path) -> None:
    work = Path(tempfile.mkdtemp(prefix="unmasker-embedded-"))
    source = work / "award-summary.fodt"
    source.write_text(FODT.format(visible=VISIBLE), encoding="utf-8")

    # The input filter is named on purpose: see the module docstring.
    odt = convert(source, work, work, "odt:writer8", "OpenDocument Text Flat XML")
    docx = convert(odt, work, work, "docx:MS Word 2007 XML")

    for produced, folder, name in (
        (odt, "odt", "libreoffice-writer-embedded-sheet.odt"),
        (docx, "docx", "libreoffice-writer-embedded-sheet.docx"),
    ):
        target = out / folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(produced.read_bytes())
        print(f"{target}  {target.stat().st_size} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens"))
