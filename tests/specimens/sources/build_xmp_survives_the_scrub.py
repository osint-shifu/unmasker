#!/usr/bin/env python3
"""Build the specimen where the Info dictionary was cleaned and XMP was not.

A PDF states its metadata twice: once in the Info dictionary and once in an XMP
packet, and nothing in the format makes the two agree. Tools that "remove
metadata" very often clear one of them. The document then carries a scrubbed
Info dictionary, which is what anybody checking will look at, and an XMP packet
that still holds the author, the working title and the trail of every
application that touched the file.

That is the whole specimen: the two halves of one file disagreeing about what
the file is.

Three producers, on purpose:

    LibreOffice   writes the page and the original Info dictionary
    exiftool      does the partial scrub and writes the XMP packet

exiftool is the canonical XMP implementation and has nothing to do with this
project, so the packet is not something written to suit the parser that will
read it. LibreOffice writes no XMP at all, which is why a second producer is
needed here and was not needed for the other specimens.

Everything is invented. The name and the address are fictional, the address is
at `example.org`, which RFC 2606 reserves.

Usage:
    python3 build_xmp_survives_the_scrub.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VISIBLE = "The company will not be commenting further at this time."

# What survives the scrub, in the Info dictionary. Anybody who checks the
# obvious place finds this and stops.
SCRUBBED_TITLE = "Statement"

# What is still in the XMP packet.
AUTHOR = "Halina Nowak-Test"
WORKING_TITLE = "Statement - HOLD until legal clears"
DESCRIPTION = "Do not release before the settlement is signed."
CONTACT = "h.nowak@example.org"
ORIGINAL_ID = "uuid:3c9f77e0-0000-4000-8000-000000000001"
DERIVED_FROM = "uuid:3c9f77e0-0000-4000-8000-000000000002"

FODT = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta>
  <meta:initial-creator>{AUTHOR}</meta:initial-creator>
  <dc:title>{WORKING_TITLE}</dc:title>
 </office:meta>
 <office:body><office:text>
  <text:p>{VISIBLE}</text:p>
 </office:text></office:body>
</office:document>
"""

# The scrub, and the packet it forgets. Two `exiftool` runs, because that is
# how it happens: one tool clears the Info dictionary, and whatever wrote the
# XMP earlier is never revisited.
SCRUB = ["-PDF:Author=", "-PDF:Subject=", "-PDF:Keywords=", f"-PDF:Title={SCRUBBED_TITLE}"]

PACKET = [
    f"-XMP-dc:Creator={AUTHOR}",
    f"-XMP-dc:Title={WORKING_TITLE}",
    f"-XMP-dc:Description={DESCRIPTION}",
    f"-XMP-iptcCore:CreatorWorkEmail={CONTACT}",
    f"-XMP-xmpMM:OriginalDocumentID={ORIGINAL_ID}",
    f"-XMP-xmpMM:DerivedFromDocumentID={DERIVED_FROM}",
    "-XMP-xmp:CreatorTool=LibreOffice/24.2.7.2$Linux_X86_64",
    "-XMP-xmpMM:HistoryAction=saved",
    "-XMP-xmpMM:HistorySoftwareAgent=Acrobat Distiller 24.0 (Windows)",
    "-XMP-xmpMM:HistoryWhen=2024-04-19T16:41:00+02:00",
    "-XMP-xmpMM:HistoryChanged=/metadata",
]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, timeout=300)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-xmp-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "statement.fodt"
    src.write_text(FODT, encoding="utf-8")

    print("LibreOffice: writing the page and its Info dictionary")
    run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp / 'loprofile'}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp),
            str(src),
        ]
    )
    produced = tmp / "statement.pdf"
    if not produced.exists():
        raise RuntimeError("LibreOffice produced no PDF")

    print("exiftool: writing the XMP packet")
    run(["exiftool", "-overwrite_original", "-q", *PACKET, str(produced)])

    print("exiftool: scrubbing the Info dictionary, and only that")
    run(["exiftool", "-overwrite_original", "-q", *SCRUB, str(produced)])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
