#!/usr/bin/env python3
"""Build the PDF-carries-an-attachment specimen.

A PDF can hold whole other files. They are not on any page, no viewer shows
them without being asked, and printing the document does not print them - the
attachment travels with the file and appears nowhere in it.

The visible page here is a decision notice that says the tender was settled on
its merits and names no figure. The file carries a text note giving the reserve
price and saying one bidder knew it in advance.

Measured on the file this script writes:

    pages                  1
    visible text           a notice naming no number
    /Names/EmbeddedFiles   1 entry, `panel-note.txt`

Everything is invented: no such tender, no such panel, no such bidder.

## Why it is built this way

`pdfattach` is poppler's, and poppler is already what this corpus uses when a
measurement has to come from something other than the code under test. The
attachment is therefore written the way a real tool writes one, into
`/Names/EmbeddedFiles`, rather than assembled here from the specification -
which is the mistake `filetrail`'s HEIC reader was built on.

## The control

`libreoffice-writer-metadata-leak.pdf` is the same producer with no attachment
at all, and the detector has to stay silent on it. It is an existing specimen,
so none is added here.

Usage:

    python3 tests/specimens/sources/build_pdf_with_an_attachment.py tests/specimens/pdf
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

NOTICE = (
    "Decision notice. The panel has completed its evaluation and the contract "
    "is awarded on the merits of the submissions received. No further "
    "information is disclosed at this stage."
)

ATTACHED = (
    "Reserve price: 240000 EUR.\n"
    "Kowalski was told the reserve before bids closed.\n"
    "Do not release with the notice.\n"
)

FODT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:body><office:text>
  <text:p>{notice}</text:p>
 </office:text></office:body>
</office:document>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-attachment-"))

    source = work / "notice.fodt"
    source.write_text(FODT.format(notice=NOTICE), encoding="utf-8")

    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            "--convert-to", "pdf", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )
    plain = work / "notice.pdf"
    if not plain.exists():
        raise RuntimeError("LibreOffice produced no PDF")

    note = work / "panel-note.txt"
    note.write_text(ATTACHED, encoding="utf-8")

    target = out / "poppler-pdf-with-an-attachment.pdf"
    target.unlink(missing_ok=True)
    subprocess.run(["pdfattach", str(plain), str(note), str(target)], check=True)

    print(f"{target}  {target.stat().st_size} bytes")
    subprocess.run(["pdfdetach", "-list", str(target)], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/pdf"))
