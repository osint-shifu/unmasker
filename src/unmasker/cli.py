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
import dataclasses
import json
import shutil
import sys
from pathlib import Path

from . import __version__, about
from .findings import Finding
from .metadata.detectors import detect as detect_metadata
from .pdf.detectors import detect as detect_drawn
from .pdf.detectors import unextractable_text, unrendered_text
from .pdf.rendered import read_page_back, tools_available
from .readers import UnreadableFile, read
from .report import Style, render
from .revisions import detect as detect_revisions
from .sheets import detect as detect_sheets
from .text.invisible import scan_text
from .theme import glyphs, resolve_depth


def collect(extraction, ocr: bool = False) -> list[Finding]:
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

    # Tier 1, for readers that can see what is painted. A page with a bar over
    # its text *and* a zero-width character in it has two findings, and neither
    # is allowed to suppress the other.
    for painted in extraction.drawn:
        found.extend(detect_drawn(painted))

    # Tier 4, for readers that can see what an application agreed not to show.
    if extraction.revisions is not None:
        found.extend(detect_revisions(extraction.revisions))

    # The same statement in a workbook: a row, a column or a sheet that carries
    # an attribute saying not to draw it, and every value in it still in the
    # file.
    if extraction.sheets is not None:
        found.extend(detect_sheets(extraction.sheets))

    # Reading each page back costs a render and an OCR pass - seconds a page -
    # and needs two external binaries, which is why it was kept out
    # of the first version and is still off unless asked for.
    if ocr and extraction.source is not None:
        for painted in extraction.drawn:
            words, problems = read_page_back(extraction.source, painted.number, painted.box)
            extraction = dataclasses.replace(
                extraction, remarks=extraction.remarks + tuple(problems)
            )
            found.extend(unrendered_text(painted, words))
            found.extend(unextractable_text(painted, words))

    # Metadata is only a finding where it says something the document does not,
    # so the detector is given the document's own text to compare against.
    if extraction.metadata is not None:
        shown = "\n".join(unit.text for unit in extraction.units)
        found.extend(detect_metadata(extraction.metadata, shown))

    return sorted(found, key=lambda f: f.location.sort_key)


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
