#!/usr/bin/env python3
"""Build the DOCX tracked-changes specimen.

A tracked deletion does not remove anything. Word stores the deleted run in
`w:delText`, beside the author who deleted it and the minute they did, and a
reader whose review pane is set to show the final text sees none of it. That is
the same gap this tool reports everywhere else, arriving through a completely
different mechanism: no geometry, no colour, no invisible characters - just a
part of the file that the application has agreed not to display.

LibreOffice writes the .docx from Flat ODF, as it does for the other DOCX
specimen. Verified before this was committed: `w:del`, `w:ins`, `w:delText`,
`w:author` and `w:date` all survive the ODF-to-OOXML conversion, and an ODF
annotation becomes `word/comments.xml`.

The document is a draft settlement note because that is where this failure
actually costs something: the figure that was struck out and the sentence that
was deleted are exactly what a recipient is not supposed to have. Every
particular in it is invented, and both authors are obviously fictional.

Usage:
    python3 build_docx_tracked_changes.py OUTPUT.docx [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REVISER = "Anna Testowa"
DRAFTER = "Piotr Przyklad"

DELETED_FIGURE = "250,000 EUR"
INSERTED_FIGURE = "90,000 EUR"
DELETED_SENTENCE = "The claimant's own expert put the exposure at 1.4 million EUR."
COMMENT = "Do not send this version to the other side - the earlier figure is still in the file."

VISIBLE_LINES = [
    "This note records the position reached at the meeting of 17 April 2024.",
    "Neither party admits liability by signing it.",
]

CHANGES = f"""
  <text:changed-region xml:id="del-figure" text:id="del-figure">
   <text:deletion>
    <office:change-info>
     <dc:creator>{REVISER}</dc:creator><dc:date>2024-04-17T10:22:00</dc:date>
    </office:change-info>
    <text:p>{DELETED_FIGURE}</text:p>
   </text:deletion>
  </text:changed-region>
  <text:changed-region xml:id="ins-figure" text:id="ins-figure">
   <text:insertion>
    <office:change-info>
     <dc:creator>{REVISER}</dc:creator><dc:date>2024-04-17T10:23:00</dc:date>
    </office:change-info>
   </text:insertion>
  </text:changed-region>
  <text:changed-region xml:id="del-sentence" text:id="del-sentence">
   <text:deletion>
    <office:change-info>
     <dc:creator>{DRAFTER}</dc:creator><dc:date>2024-04-18T09:05:00</dc:date>
    </office:change-info>
    <text:p>{DELETED_SENTENCE}</text:p>
   </text:deletion>
  </text:changed-region>
"""


def fodt() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
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
   <style:paragraph-properties fo:margin-bottom="0.35cm"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:tracked-changes>{CHANGES}</text:tracked-changes>
  <text:p text:style-name="Head">DRAFT SETTLEMENT NOTE - SYNTHETIC</text:p>
  <text:p text:style-name="Body">{VISIBLE_LINES[0]}</text:p>
  <text:p text:style-name="Body">The parties agree to settle for <text:change
   text:change-id="del-figure"/><text:change-start
   text:change-id="ins-figure"/>{INSERTED_FIGURE}<text:change-end
   text:change-id="ins-figure"/>, payable within thirty days.<text:change
   text:change-id="del-sentence"/></text:p>
  <text:p text:style-name="Body">{VISIBLE_LINES[1]}<office:annotation>
    <dc:creator>{REVISER}</dc:creator><dc:date>2024-04-19T11:00:00</dc:date>
    <text:p>{COMMENT}</text:p>
   </office:annotation></text:p>
 </office:text></office:body>
</office:document>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-tracked-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "settlement-note.fodt"
    src.write_text(fodt(), encoding="utf-8")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp / 'loprofile'}",
            "--convert-to",
            "docx",
            "--outdir",
            str(tmp),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    out = tmp / "settlement-note.docx"
    if not out.exists():
        raise RuntimeError("LibreOffice produced no .docx")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
