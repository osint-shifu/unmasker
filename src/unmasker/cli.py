"""The command line.

Modes are commands, not flags - `CLAUDE.md` - so there is exactly one thing to
do here and no mode switch. `--json` changes the shape of the output, not what
the tool did, which is what keeps it a flag.

Exit codes, and why there are three rather than two:

    0   read, searched, nothing found
    1   read, searched, findings exist
    2   could not be read

`HANDOFF.md` records the decision that there is no `--strict`: 1 is the CI gate
already. But 2 has to be distinct from 0, because a file that could not be read
is not a file that came back clean, and a pipeline that cannot tell those apart
will eventually wave through the one document it should have stopped.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .findings import Finding
from .readers import UnreadableFile, read
from .report import Style, render
from .text.invisible import scan_text
from .theme import glyphs, resolve_depth


def collect(extraction) -> list[Finding]:
    """Run every text detector over every unit, tagging findings with the page.

    Detectors are additive and none outranks another: a unit with a bidi
    override and a homoglyph produces two findings, and nothing here filters
    one against the other.
    """
    found: list[Finding] = []
    for unit in extraction.units:
        for finding in scan_text(unit.text):
            if unit.page is not None:
                finding = dataclasses.replace(
                    finding,
                    location=dataclasses.replace(finding.location, page=unit.page),
                )
            found.append(finding)
    return sorted(found, key=lambda f: f.location.sort_key)


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
    parser.add_argument("file", type=Path, help="the document to read")
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
    parser.add_argument("--version", action="version", version=f"unmasker {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        extraction = read(args.file)
    except UnreadableFile as exc:
        print(f"unmasker: {exc}", file=sys.stderr)
        return 2

    findings = collect(extraction)

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
        width = args.width or min(100, max(50, shutil.get_terminal_size((78, 24)).columns))
        style = Style(depth=resolve_depth(sys.stdout), width=width, glyph=glyphs(sys.stdout))
        sys.stdout.write(render(str(args.file), extraction, findings, style))

    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
