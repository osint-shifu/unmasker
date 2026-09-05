#!/usr/bin/env python3
"""Build the legacy Word 97 specimen.

`.doc` is not a zip and not XML. It is a **compound file**: a whole FAT
filesystem inside one file, with sectors, an allocation table, a directory
tree, and a second smaller filesystem inside it for streams below 4096 bytes.
Nothing in the standard library reads one.

What that filesystem holds here is `\\x05SummaryInformation` and
`\\x05DocumentSummaryInformation` - the author, the title, the company and the
edit count - none of which appears on the page.

Measured on the file this script writes:

    streams          7, of which every useful one is under 4096 bytes
    the useful ones  therefore live in the mini stream, not in sectors
    visible text     an award notice naming nobody

That second line is the reason this specimen exists before the reader does. A
compound-file reader written from the specification would be entitled to leave
the mini stream for later, and against this file it would read **nothing at
all** - which is how `filetrail`'s HEIC reader passed a full test suite while
decoding no HEIC ever written.

Everything in the metadata is invented.

Usage:

    python3 tests/specimens/sources/build_legacy_word.py tests/specimens/doc
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

FODT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta>
  <meta:initial-creator>Halina Probna-Test</meta:initial-creator>
  <dc:creator>Marek Zapasowy-Przyklad</dc:creator>
  <dc:title>Panel copy - do not circulate</dc:title>
  <dc:subject>Tender evaluation</dc:subject>
  <meta:keyword>reserve; internal</meta:keyword>
  <meta:editing-cycles>23</meta:editing-cycles>
  <meta:user-defined meta:name="Company">Osint Shifu sp. z o.o.</meta:user-defined>
 </office:meta>
 <office:body><office:text>
  <text:p>Award notice. The contract has been awarded and the file is closed.</text:p>
 </office:text></office:body>
</office:document>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-legacy-"))

    source = work / "award.fodt"
    source.write_text(FODT, encoding="utf-8")
    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            "--convert-to", "doc", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )

    produced = work / "award.doc"
    data = produced.read_bytes()
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise RuntimeError("LibreOffice did not write a compound file")

    target = out / "libreoffice-writer-word97.doc"
    target.write_bytes(data)
    print(f"{target}  {len(data)} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/doc"))
