#!/usr/bin/env python3
"""Build the metadata-leak specimen, in both containers from one source.

The document's visible text is one anonymous sentence. Its metadata names two
people, a client, a codename, a classification and a path on somebody's home
directory. Every one of those is read by any parser and shown to no reader.

Two outputs from the same source, because the containers carry different
amounts of it. The .docx keeps the custom properties, the editing time and the
revision count; the PDF keeps the author, title, subject and keywords and drops
the rest. A tool that had only ever been tried on one of them would have a
confident and partial idea of what metadata is.

`Application` in the .docx comes out as `LibreOffice/24.2.7.2$Linux_X86_64
LibreOffice_project/420$Build-2`. That string is the worked example in
`CLAUDE.md`: it contains a dotted quad, pattern-matching alone reports an IP
address, and the field is called `Application`, so it is a version. There is a
test that holds the tool to reading it as one.

Everything here is invented. Both names are obviously fictional, the client and
the codename do not exist, and the path is not anybody's.

Usage:
    python3 build_metadata_leak.py OUT.docx OUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

INITIAL_AUTHOR = "Marek Wysocki-Test"
LAST_EDITOR = "Ewa Zielinska-Test"
TITLE = "Board briefing - restricted"
SUBJECT = "Project Harrow"
KEYWORDS = "confidential, do not circulate"
CLIENT = "Acme Holdings BV"
TEMPLATE_PATH = "/home/mwysocki/Templates/acme-board-restricted.ott"

# The only thing a reader of this document ever sees.
VISIBLE = "The board notes the position and will revert in due course."


def fodt() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta>
  <meta:initial-creator>{INITIAL_AUTHOR}</meta:initial-creator>
  <dc:creator>{LAST_EDITOR}</dc:creator>
  <meta:creation-date>2024-03-02T08:14:00</meta:creation-date>
  <dc:date>2024-04-19T16:41:00</dc:date>
  <dc:title>{TITLE}</dc:title>
  <dc:subject>{SUBJECT}</dc:subject>
  <meta:keyword>{KEYWORDS}</meta:keyword>
  <meta:editing-cycles>37</meta:editing-cycles>
  <meta:editing-duration>PT4H12M</meta:editing-duration>
  <meta:user-defined meta:name="Client">{CLIENT}</meta:user-defined>
  <meta:user-defined meta:name="SourceTemplate">{TEMPLATE_PATH}</meta:user-defined>
 </office:meta>
 <office:body><office:text>
  <text:p>{VISIBLE}</text:p>
 </office:text></office:body>
</office:document>
"""


def convert(src: Path, workdir: Path, fmt: str) -> Path:
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{workdir / 'loprofile'}",
            "--convert-to",
            fmt,
            "--outdir",
            str(workdir),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    out = workdir / f"{src.stem}.{fmt}"
    if not out.exists():
        raise RuntimeError(f"LibreOffice produced no .{fmt} for {src}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("docx", type=Path)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-metadata-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "board-briefing.fodt"
    src.write_text(fodt(), encoding="utf-8")

    for target, fmt in ((args.docx, "docx"), (args.pdf, "pdf")):
        produced = convert(src, tmp, fmt)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, target)
        print(f"wrote {target} ({target.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
