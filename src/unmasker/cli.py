"""The command line.

Modes are commands, not flags - `CONTRIBUTING.md` - so there is exactly one thing to
do here and no mode switch. `--json` changes the shape of the output, not what
the tool did, which is what keeps it a flag.

Exit codes, and why there are three rather than two:

    0   read, searched, nothing found
    1   read, searched, findings exist
    2   could not be read

There is deliberately no `--strict`: 1 is the CI gate already. But 2 has to be
distinct from 0, because a file that could not be read is not a file that came
back clean, and a pipeline that cannot tell those apart will eventually wave
through the one document it should have stopped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__, about
from .detect import collect
from .pdf.rendered import tools_available
from .readers import UnreadableFile, read
from .report import Style, render
from .theme import glyphs, resolve_depth


def _style(width: int | None) -> Style:
    """One place that decides how wide the output is and how much colour it may
    use, so the report and the landing screen can never disagree about it."""
    return Style(
        depth=resolve_depth(sys.stdout),
        width=width or min(100, max(50, shutil.get_terminal_size((78, 24)).columns)),
        glyph=glyphs(sys.stdout),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unmasker",
        description=(
            "Report what a human sees in a document against what a machine "
            "reads out of it, and name every place the two disagree."
        ),
        epilog=(
            "Exit status is 0 when nothing was found, 1 when there are "
            "findings, and 2 when the file could not be read."
        ),
    )
    # Optional, so a bare `unmasker` can introduce itself instead of printing
    # `error: the following arguments are required`, which tells a reader they
    # were wrong and nothing else.
    parser.add_argument("file", type=Path, nargs="?", help="the document to read")
    # A description that restates its flag teaches the reader to skip
    # descriptions, and once they skip one they skip the rest.
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit one JSON object on stdout for a pipeline to sort or filter",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        metavar="N",
        help="wrap the report at N columns instead of measuring the terminal",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help=(
            "render each page and read it back, to find words the file holds "
            "that the page does not show - and the reverse. Needs ghostscript "
            "and tesseract, and costs seconds a page, which is why it is not "
            "the default"
        ),
    )
    parser.add_argument("--version", action="version", version=f"unmasker {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.file is None:
        # Nothing was read and nothing was searched, so this is not a result:
        # exit 0 means "no findings", and a screen that introduces the tool has
        # no findings to report.
        sys.stdout.write(about.render(_style(args.width)))
        return 0

    try:
        extraction = read(args.file)
    except UnreadableFile as exc:
        print(f"unmasker: {exc}", file=sys.stderr)
        return 2

    if args.ocr:
        present, missing = tools_available()
        if not present:
            print(
                "unmasker: --ocr needs " + " and ".join(missing) + " on PATH",
                file=sys.stderr,
            )
            return 2

    findings = collect(extraction, ocr=args.ocr)

    if args.json:
        json.dump(
            {
                "tool": "unmasker",
                "version": __version__,
                "file": str(args.file),
                "kind": extraction.kind,
                # The machine-readable half of "nothing found has two
                # meanings". False here means there was nothing to search, not
                # that the search came back empty.
                "searched": extraction.has_text,
                "remarks": list(extraction.remarks),
                "findings": [f.as_dict() for f in findings],
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render(str(args.file), extraction, findings, _style(args.width)))

    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
