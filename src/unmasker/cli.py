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

from . import SCHEMA, __version__, about
from .detect import collect
from .html import render_file as render_html
from .html import render_survey as render_survey_html
from .markdown import render_file as render_md
from .markdown import render_survey as render_survey_md
from .pdf.rendered import tools_available
from .readers import UnreadableFile, read
from .report import Style, render
from .scan import survey
from .survey_report import as_json, render_survey
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
    parser.add_argument(
        "file", type=Path, nargs="?", help="the document to read, or a folder of them"
    )
    # A description that restates its flag teaches the reader to skip
    # descriptions, and once they skip one they skip the rest.
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit one JSON object on stdout for a pipeline to sort or filter",
    )
    parser.add_argument(
        "--md",
        action="store_true",
        help=(
            "emit Markdown on stdout, for a wiki, a ticket or a pull request. "
            "Every value is fenced or escaped, because a Markdown renderer "
            "passes raw HTML straight through"
        ),
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help=(
            "emit one self-contained HTML document on stdout, to redirect into "
            "a file somebody can be sent. Carries the full detail, loads "
            "nothing from anywhere, and runs no script"
        ),
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


def _directory(args) -> int:
    """A folder of documents, surveyed rather than reported one at a time.

    The exit code says the same three things it says about a file, one level
    up. 2 is reserved for *nothing here could be read*, because a pipeline
    handed a folder of unreadable files must not be told it came back clean.
    """
    if args.ocr:
        # Seconds a page across a case folder is hours. Saying so beats
        # starting and leaving somebody to wonder whether it hung.
        print(
            "unmasker: --ocr is a page at a time and costs seconds a page; "
            "it is refused on a directory. Run it on the file you want.",
            file=sys.stderr,
        )
        return 2

    found = survey(args.file)

    if args.json:
        json.dump(as_json(found), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    elif args.html:
        sys.stdout.write(render_survey_html(found))
    elif args.md:
        sys.stdout.write(render_survey_md(found))
    else:
        sys.stdout.write(render_survey(found, _style(args.width)))

    if found.results and not found.read:
        return 2
    return 1 if found.hiding else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.file is None:
        # Nothing was read and nothing was searched, so this is not a result:
        # exit 0 means "no findings", and a screen that introduces the tool has
        # no findings to report.
        sys.stdout.write(about.render(_style(args.width)))
        return 0

    chosen = [name for name in ("json", "html", "md") if getattr(args, name)]
    if len(chosen) > 1:
        # Two shapes of output down one pipe is one of them corrupted.
        print(
            "unmasker: " + " and ".join(f"--{name}" for name in chosen)
            + " all write to stdout; choose one",
            file=sys.stderr,
        )
        return 2

    if args.file.is_dir():
        return _directory(args)

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
                "schema": f"unmasker.scan/{SCHEMA}",
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
    elif args.html:
        sys.stdout.write(render_html(args.file, extraction, findings))
    elif args.md:
        sys.stdout.write(render_md(args.file, extraction, findings))
    else:
        sys.stdout.write(render(str(args.file), extraction, findings, _style(args.width)))

    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
