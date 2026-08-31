#!/usr/bin/env python3
"""Build the OpenDocument specimen.

`unmasker` refused .odt files outright until this existed - "it looks like an
OpenDocument file, which unmasker does not read yet". That is a large refusal:
ODF is LibreOffice's native format and the one a great deal of European
government and legal work is written in, and it carries every kind of thing
this tool looks for.

This document has six of them at once:

    a tracked deletion   the earlier figure, struck out and still in the file
    a tracked insertion  what replaced it, which is on the page and is not hidden
    a comment            mid-sentence, with the rest of the sentence after it
    a header             in styles.xml, which is a second part to read
    metadata             an author, a working title and a custom property
    a zero-width space   inside an address, in the body text

The insertion and the header are here because mutation testing asked for them:
without an insertion nothing distinguished the two kinds of region, and without
a header nothing said `styles.xml` was read at all. The comment sits
mid-sentence for the same reason - skipping a subtree must not swallow what
follows it on the line, and a comment at the end of a paragraph never tests
that.

Being ODF, it is written by LibreOffice as its *own* format rather than
converted into somebody else's, so nothing here depends on the fidelity of an
export filter - which is a question every other specimen in this directory has
had to answer.

Everything is invented; the address is at `example.org`, reserved by RFC 2606.

Usage:
    python3 build_odf_document.py OUTPUT.odt [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AUTHOR = "Halina Probna-Test"
TITLE = "Position note - internal only"
DELETED = "the earlier estimate of 3.1 million"
INSERTED = "a figure to be settled"
COMMENT = "Do not share the working file with the other side."
ZWSP = "​"
CONTACT = f"h.probna{ZWSP}@example.org"

VISIBLE = "The figure is withheld pending advice."
AFTER_COMMENT = "The panel meets again in June."
HEADER = "POSITION NOTE - DRAFT"
CLIENT = "Meridian Trust BV"

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
  <dc:title>{TITLE}</dc:title>
  <meta:editing-cycles>12</meta:editing-cycles>
  <meta:user-defined meta:name="Client">{CLIENT}</meta:user-defined>
 </office:meta>
 <office:automatic-styles>
  <style:style style:name="Head" style:family="paragraph">
   <style:paragraph-properties fo:margin-bottom="0.5cm"/>
   <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
  </style:style>
  <style:page-layout style:name="PL">
   <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"
    fo:margin-top="2cm" fo:margin-bottom="2cm"
    fo:margin-left="2.5cm" fo:margin-right="2.5cm">
    <style:header-footer-properties fo:min-height="0.6cm"/>
   </style:page-layout-properties>
  </style:page-layout>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="PL">
   <style:header><text:p>{HEADER}</text:p></style:header>
  </style:master-page>
 </office:master-styles>
 <office:body><office:text>
  <text:tracked-changes>
   <text:changed-region xml:id="del1" text:id="del1">
    <text:deletion>
     <office:change-info>
      <dc:creator>{AUTHOR}</dc:creator><dc:date>2024-05-06T09:11:00</dc:date>
     </office:change-info>
     <text:p>{DELETED}</text:p>
    </text:deletion>
   </text:changed-region>
   <text:changed-region xml:id="ins1" text:id="ins1">
    <text:insertion>
     <office:change-info>
      <dc:creator>{AUTHOR}</dc:creator><dc:date>2024-05-06T09:14:00</dc:date>
     </office:change-info>
    </text:insertion>
   </text:changed-region>
  </text:tracked-changes>
  <text:p text:style-name="Head">POSITION NOTE - SYNTHETIC</text:p>
  <text:p>{VISIBLE}<text:change text:change-id="del1"/> It is now <text:change-start
   text:change-id="ins1"/>{INSERTED}<text:change-end
   text:change-id="ins1"/>.<office:annotation>
    <dc:creator>{AUTHOR}</dc:creator><dc:date>2024-05-06T09:20:00</dc:date>
    <text:p>{COMMENT}</text:p>
   </office:annotation> {AFTER_COMMENT}</text:p>
  <text:p>Queries to {CONTACT} in the first instance.</text:p>
 </office:text></office:body>
</office:document>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-odf-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "position-note.fodt"
    src.write_text(FODT, encoding="utf-8")

    subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp / 'loprofile'}",
            "--convert-to",
            "odt",
            "--outdir",
            str(tmp),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    out = tmp / "position-note.odt"
    if not out.exists():
        raise RuntimeError("LibreOffice produced no .odt")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
