#!/usr/bin/env python3
"""Build the PDF whose comments are still in it.

A comment in a PDF is an annotation: a dictionary hanging off the page with the
text in `/Contents` and the author in `/T`. It is not part of the page. It does
not print, `pdftotext` does not report it, and a reader looking at the document
never meets it - but it is in the file, and every PDF library reads it in one
line.

This is the same finding as a DOCX comment, arriving through a completely
different mechanism, and it needed a specimen because `unmasker` read only the
page's content stream and never looked at `/Annots` at all.

LibreOffice does not export comments by default. It has to be asked:

    --convert-to 'pdf:writer_pdf_Export:{"ExportNotes":{...,"value":"true"}}'

which is worth knowing, because it means a document can lose its comments on
export without anybody choosing that, and gain them the same way.

Everything is invented.

Usage:
    python3 build_pdf_with_comments.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REVIEWER = "Anna Testowa"
DRAFTER = "Piotr Przyklad"

FIRST = "Only because the alternative was litigation. Do not minute this."
SECOND = "Check whether the figure has to be disclosed at all."

VISIBLE = [
    "The board approved the revised terms without dissent.",
    "The chair thanked the committee for its work.",
]

FODT = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 office:version="1.3"
 office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="Head" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.5cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Body" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.4cm"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:p text:style-name="Head">BOARD MINUTE - SYNTHETIC</text:p>
  <text:p text:style-name="Body">{VISIBLE[0]}<office:annotation>
    <dc:creator>{REVIEWER}</dc:creator><dc:date>2024-04-19T11:00:00</dc:date>
    <text:p>{FIRST}</text:p>
   </office:annotation></text:p>
  <text:p text:style-name="Body">{VISIBLE[1]}<office:annotation>
    <dc:creator>{DRAFTER}</dc:creator><dc:date>2024-04-20T08:30:00</dc:date>
    <text:p>{SECOND}</text:p>
   </office:annotation></text:p>
 </office:text></office:body>
</office:document>
"""

# LibreOffice drops comments on PDF export unless it is told not to.
FILTER = 'pdf:writer_pdf_Export:{"ExportNotes":{"type":"boolean","value":"true"}}'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-comments-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "board-minute.fodt"
    src.write_text(FODT, encoding="utf-8")

    subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp / 'loprofile'}",
            "--convert-to",
            FILTER,
            "--outdir",
            str(tmp),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    out = tmp / "board-minute.pdf"
    if not out.exists():
        raise RuntimeError("LibreOffice produced no PDF")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
