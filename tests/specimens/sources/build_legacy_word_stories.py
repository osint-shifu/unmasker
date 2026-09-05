#!/usr/bin/env python3
"""Build the Word 97 specimen whose text is mostly not in the main story.

A `.doc` does not hold one run of text. It holds several, laid end to end in a
single character-position space, and the FIB says how long each is: `ccpText`,
then `ccpFtn`, `ccpHdd`, `ccpAtn`, `ccpEdn`, `ccpTxbx`, `ccpHdrTxbx`. Footnotes,
headers and footers, comments, endnotes and text boxes are each a *story* of
their own, and none of them is in the main one.

Measured on the file this script writes:

    ccpText      221 characters   the paragraphs on the page
    everything   458 characters   what the file actually holds

**Less than half of this document's text is in `ccpText`.** A reader that took
the main story and stopped would search 48% of the file and then report that it
had searched it - and the half it skipped is the half worth reading: a comment
naming the second bidder, a header marked *internal circulation only*, a
footnote about a withdrawal, a text box saying the figures are not approved.

That is the `filetrail` HEIC failure in a new costume, and it is why this file
exists before the reader that reads it.

Three more things are here because a real producer writes them and a
specification reader would not think to build them:

**The hyperlink is a field.** The bytes hold
`0x13 HYPERLINK "https://..." 0x14 published summary 0x15` - an instruction, a
separator, and the result. The page shows the result. Text extraction that
concatenates the run reports a URL as though somebody could read it on the
page, which would make the visible text wrong for every detector downstream.

**The table is not tab-separated.** Cells end with `0x07`, and so do rows.

**The text is UTF-16, not the compressed 8-bit form**, even though every
character in the main paragraph is ASCII. The specification presents the 8-bit
piece as the ordinary case; LibreOffice never writes one.

Everything in the metadata and the text is invented.

Usage:

    python3 tests/specimens/sources/build_legacy_word_stories.py tests/specimens/doc
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
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:meta>
  <meta:initial-creator>Halina Probna-Test</meta:initial-creator>
  <dc:creator>Marek Zapasowy-Przyklad</dc:creator>
  <dc:title>Scoring pack - not for release</dc:title>
 </office:meta>
 <office:automatic-styles>
  <style:page-layout style:name="pm1">
   <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm"/>
   <style:header-style/><style:footer-style/>
  </style:page-layout>
  <style:style style:name="fr1" style:family="graphic">
   <style:graphic-properties svg:width="6cm" svg:height="2cm" style:wrap="none"/>
  </style:style>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="pm1">
   <style:header><text:p>Draft header - internal circulation only</text:p></style:header>
   <style:footer><text:p>Footer: reviewed by the panel secretary</text:p></style:footer>
  </style:master-page>
 </office:master-styles>
 <office:body><office:text>
  <text:p>Award notice. The contract has been awarded and the file is closed.</text:p>
  <text:p>See the <text:a
   xlink:href="https://internal.example.invalid/tender/2019/final-scores"
   >published summary</text:a> for the scores.<text:note
   text:id="ftn1" text:note-class="footnote"><text:note-citation>1</text:note-citation
   ><text:note-body><text:p>Footnote: the second bidder withdrew before scoring.</text:p
   ></text:note-body></text:note></text:p>
  <text:p>Zamowienie rozstrzygniete<office:annotation
   ><dc:creator>Halina Probna-Test</dc:creator><text:p
   >Comment: we should not name the second bidder here.</text:p
   ></office:annotation> - koniec postepowania.</text:p>
  <table:table table:name="Scores">
   <table:table-column table:number-columns-repeated="2"/>
   <table:table-row><table:table-cell><text:p>Bidder</text:p></table:table-cell
    ><table:table-cell><text:p>Score</text:p></table:table-cell></table:table-row>
   <table:table-row><table:table-cell><text:p>Wykonawca A</text:p></table:table-cell
    ><table:table-cell><text:p>84</text:p></table:table-cell></table:table-row>
  </table:table>
  <text:p><draw:frame draw:style-name="fr1" text:anchor-type="paragraph"
   svg:width="6cm" svg:height="2cm"><draw:text-box><text:p
   >Text box: figures not yet approved.</text:p></draw:text-box></draw:frame></text:p>
 </office:text></office:body>
</office:document>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="unmasker-stories-"))

    source = work / "scoring.fodt"
    source.write_text(FODT, encoding="utf-8")
    subprocess.run(
        [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{work / 'loprofile'}",
            # Named explicitly: a flat ODF whose body holds a table is
            # otherwise detected as a Calc document and converted as one.
            "--infilter=OpenDocument Text Flat XML",
            "--convert-to", "doc", "--outdir", str(work), str(source),
        ],
        check=True, capture_output=True, timeout=300,
    )

    produced = work / "scoring.doc"
    data = produced.read_bytes()
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise RuntimeError("LibreOffice did not write a compound file")

    target = out / "libreoffice-writer-word97-stories.doc"
    target.write_bytes(data)
    print(f"{target}  {len(data)} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "tests/specimens/doc"))
