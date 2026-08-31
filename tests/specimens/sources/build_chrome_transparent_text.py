#!/usr/bin/env python3
"""Build the specimen for text that is painted at zero opacity.

`color: transparent` is one CSS declaration. The glyphs are laid out, shaped
and painted exactly as any other text; the paint is simply not opaque. Nothing
is drawn over them, no render mode is changed, and the text selects, searches
and copies out of the page like any other.

This specimen exists because probing turned up a hole rather than because a gap
list named one. Chrome does **not** use render mode 3 for transparent text - it
sets `/ca 0` in an `ExtGState` and paints normally - so a detector that looked
only at `Tr` would find nothing here, and a detector that looked only at colour
would find black text on white paper and call it perfectly legible.

Everything is invented.

Usage:
    python3 build_chrome_transparent_text.py OUTPUT.pdf [--workdir DIR]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VISIBLE = "This paragraph is ordinary black text and must not be reported."
TRANSPARENT = "The reserve price is 4.2 million and we will go to 5 if pushed."
FADED = "This line is set at one tenth opacity and is very nearly not there."

HTML = f"""<!doctype html>
<meta charset="utf-8">
<title>Bidding note</title>
<style>
  @page {{ size: A4; margin: 25mm; }}
  body {{ font: 12pt/1.7 "Liberation Serif", serif; color: #000; }}
  h1 {{ font-size: 15pt; margin: 0 0 14pt; }}
  p {{ margin: 0 0 10pt; }}

  /* One declaration. The glyphs are still painted, just not opaquely. */
  .transparent {{ color: transparent; }}
  .faded {{ opacity: 0.1; }}
</style>
<h1>BIDDING NOTE - SYNTHETIC</h1>
<p>{VISIBLE}</p>
<p class="transparent">{TRANSPARENT}</p>
<p class="faded">{FADED}</p>
<p>Three paragraphs above. Only two of them can be read from the page.</p>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--workdir", type=Path, default=None)
    args = ap.parse_args()

    tmp = args.workdir or Path(tempfile.mkdtemp(prefix="unmasker-transparent-"))
    tmp.mkdir(parents=True, exist_ok=True)

    src = tmp / "bidding-note.html"
    src.write_text(HTML, encoding="utf-8")
    out = tmp / "bidding-note.pdf"

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
