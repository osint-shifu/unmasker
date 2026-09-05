#!/usr/bin/env python3
"""Build the incremental-update specimen.

A PDF is not rewritten when it is edited. It is **appended to**: the original
bytes stay exactly where they were, and a new cross-reference section listing
the changed objects is written after them, ending in a second `%%EOF`. Every
earlier revision of the document is still in the file.

Delete a page this way and the page does not go anywhere. The new catalogue
stops pointing at it, every viewer stops showing it, and the text is still
there for anything that reads the earlier revision.

Measured on the file this script writes:

    revision 1   2 pages, holding "ANNEX A. Reserve price 240000 EUR."
    revision 2   1 page, holding neither the annex nor the figure
    the file     both, one after the other, 12637 bytes

## Producers, and why two of them

LibreOffice writes the two-page document. **pypdf** performs the incremental
delete, because it is a real writer used in real pipelines and it decides the
byte layout of the update, not this script - a layout invented here would only
prove the detector can read what this repository invented, which is the mistake
`filetrail`'s HEIC reader was built on.

pypdf is also this project's own parser, so the specimen is checked against
`qpdf`, an independent implementation, and the detector reads revision
boundaries out of the raw bytes rather than asking pypdf where they are.

Everything is invented: no such award, no such annex, no such bidder.

Usage:

    python3 tests/specimens/sources/build_incremental_update.py tests/specimens/pdf
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
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="Break" style:family="paragraph"
   style:parent-style-name="Standard">
   <style:paragraph-properties fo:break-before="page"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:p>Award notice. The contract has been awarded and the file is closed.</text:p>
  <text:p text:style-name="Break">ANNEX A. Reserve price 240000 EUR. Kowalski
   told before bids closed.</text:p>
 </office:text></office:body>
</office:document>
"""


def main(out: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-incremental-"))

    source = work / "award.fodt"
    source.write_text(FODT, encoding="utf-8")
    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            "--convert-to", "pdf", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )

    original = work / "award.pdf"
    if len(PdfReader(original).pages) != 2:
        raise RuntimeError("the page break did not take; the annex is not its own page")

    target = out / "pypdf-incremental-page-removed.pdf"
    writer = PdfWriter(fileobj=str(original), incremental=True)
    del writer.pages[1]
    with target.open("wb") as handle:
        writer.write(handle)

    before = original.read_bytes()
    after = target.read_bytes()
    if not after.startswith(before):
        raise RuntimeError("this is not an incremental update: the original bytes moved")

    print(f"{target}  {len(after)} bytes")
    print(f"  revisions by %%EOF: {after.count(b'%%EOF')}")
    print(f"  pages now: {len(PdfReader(target).pages)}")
    subprocess.run(["qpdf", "--check", str(target)], capture_output=True)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/pdf"))
