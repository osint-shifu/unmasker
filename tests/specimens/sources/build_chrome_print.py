#!/usr/bin/env python3
"""Build the Chrome print-to-PDF failed-redaction specimen.

A second producer, with a different rendering engine (Skia), because one
producer is an anecdote. If two independent engines agree on how they emit a
filled black box, the detector can rely on it; if they disagree, the detector
has to handle both, and it is much cheaper to learn that now than after the
interpreter is written.

The redaction here is a CSS overlay - an absolutely positioned black box
stretched over an inline span. That is how a web page hides something, and
printing such a page is a real route to a released PDF. The text is painted
first and the box on top of it, so nothing is removed from the document.

Everything in the document is invented. The e-mail domain is `example.org`,
reserved by RFC 2606.

Usage:
    python3 build_chrome_print.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Same particulars as the LibreOffice specimen, so a test can compare what two
# different producers do with identical content.
FIELDS = [
    ("Name", "Wanda Testowa-Przyklad", True),
    ("Email", "w.testowa@example.org", True),
    ("Telephone", "+48 601 000 000", True),
    ("Address", "ul. Przykladowa 12/3, 00-001 Warszawa", True),
    ("Filed", "17 April 2024", False),
    ("Registry", "SYN-2024-0417", False),
]

HTML = """<!doctype html>
<meta charset="utf-8">
<title>Synthetic disclosure</title>
<style>
  @page {{ size: A4; margin: 25mm; }}
  body {{ font: 11pt/1.9 "Liberation Serif", serif; color: #000; }}
  h1 {{ font-size: 14pt; margin: 0 0 12pt; }}
  p  {{ margin: 0 0 10pt; }}
  table {{ border-collapse: collapse; font-family: "Liberation Mono", monospace; }}
  td {{ padding: 2pt 0; vertical-align: baseline; }}
  td.k {{ padding-right: 14pt; white-space: nowrap; }}

  /* The redaction. The span keeps its text; the child box is painted over it.
     Nothing is removed - which is the entire point of the specimen. */
  .hide {{ position: relative; }}
  .hide > i {{
    position: absolute;
    left: -3px; right: -3px; top: -1px; bottom: -1px;
    background: #000;
  }}
</style>
<h1>SYNTHETIC DISCLOSURE - NOT A REAL CASE</h1>
<p>The identifying particulars of the complainant are set out below.
   They have been redacted prior to release.</p>
<table>{rows}</table>
<p style="margin-top:18pt">This file is a test specimen for the unmasker
   project. Every particular in it is invented.</p>
"""


def html() -> str:
    rows = []
    for label, value, redact in FIELDS:
        cell = f'<span class="hide">{value}<i></i></span>' if redact else value
        rows.append(f'<tr><td class="k">{label}:</td><td>{cell}</td></tr>')
    return HTML.format(rows="".join(rows))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-chrome-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "disclosure.html"
    src.write_text(html(), encoding="utf-8")
    out = tmp / "chrome.pdf"

    subprocess.run(
        [
            "google-chrome",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={tmp / 'chromeprofile'}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out}",
            src.as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    if not out.exists():
        raise RuntimeError("Chrome produced no PDF")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")

    if args.workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
