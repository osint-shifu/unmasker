"""The screen a directory produces, and the record a pipeline gets.

The single-file report answers *what is hidden in this document*. This answers
*which of these do I need to open*, which is a different question and needs a
shorter answer: a folder of two hundred files, each printed in full, is a
scroll rather than a report.

So **the screen triages and `--json` is the archive.** That split needs no new
flag and no `--full`, which is the sort of mode this project turns into a
command rather than an option. The complete record already exists in
machine-readable form, so the screen is free to be short - and a reader who
wants the detail on one file runs the tool on that file, which is the command
the screen prints at the bottom.

## What it must never do

**Rank.** Files are listed in path order. The tally counts files per kind, and
says `file` beside the number so nobody reads it as a count of findings. There
is no score, no percentage and no word of judgement anywhere in it - a survey
that sorted the worst documents to the top would have made exactly the decision
`CONTRIBUTING.md` says belongs to the reader.

**Let the refusals become a footnote.** Twelve unreadable files and a cheerful
`nothing hidden found` is the misleading report this project exists to avoid,
so the refusals are a section with the same weight as the findings, and each
one keeps the reason in the reader's own words.
"""

from __future__ import annotations

import textwrap

from . import __version__
from .report import MARGIN, Style, _header, _rule
from .scan import Survey
from .theme import FAINT, FOREGROUND, MUTED

INDENT = MARGIN + "  "


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _rows(style: Style, rows: list[tuple[str, str]], width: int) -> list[str]:
    """A name and what is beside it, the left column sized to this section.

    Nothing is truncated - a path clipped by an ellipsis is the one value a
    reader cannot go and look up another way - so a name too long for the
    column takes the line to itself and its detail goes underneath.
    """
    if not rows:
        return []
    left = max(len(name) for name, _ in rows)
    room = width - len(INDENT) - left - 2

    out: list[str] = []
    for name, detail in rows:
        if room < 20:
            out.append(INDENT + style.ink(name, FOREGROUND))
            wrapped = textwrap.wrap(
                detail, width=max(12, width - len(INDENT) - 2), break_on_hyphens=False
            )
            for line in wrapped:
                out.append(INDENT + "  " + style.ink(line, MUTED))
            continue
        # Never at a hyphen: `tag-characters` split across two lines is no
        # longer a name a reader can search the report for.
        lines = textwrap.wrap(detail, width=room, break_on_hyphens=False) or [""]
        out.append(
            INDENT + style.ink(name.ljust(left), FOREGROUND) + "  " + style.ink(lines[0], MUTED)
        )
        for extra in lines[1:]:
            out.append(INDENT + " " * (left + 2) + style.ink(extra, MUTED))
    return out


def _relative(survey: Survey, result) -> str:
    try:
        return str(result.path.relative_to(survey.root))
    except ValueError:
        return str(result.path)


def render_survey(survey: Survey, style: Style | None = None) -> str:
    style = style or Style()
    width = style.width

    hiding = survey.hiding
    refused = survey.refused
    read = survey.read

    out: list[str] = [""]
    name = style.ink("unmasker", FOREGROUND, bold=True)
    count = (
        f"{len(hiding)} of {_plural(len(survey.results), 'file')}"
        if survey.results
        else "no files to read"
    )
    root = str(survey.root)
    # One space at minimum between the path and the count, so the two never
    # read as a single string.
    spent = len(MARGIN) + len("unmasker") + 2 + len(root) + len(count)
    if spent < width:
        pad = width - spent
        out.append(
            MARGIN + name + "  " + style.ink(root, FAINT) + " " * pad + style.ink(count, MUTED)
        )
    else:
        # A path too long to share the line gets its own, wrapped rather than
        # cut: a truncated directory is one a reader cannot go and open.
        pad = max(1, width - len(MARGIN) - len("unmasker") - len(count))
        out.append(MARGIN + name + " " * pad + style.ink(count, MUTED))
        for line in textwrap.wrap(root, width=width - len(INDENT)) or [root]:
            out.append(INDENT + style.ink(line, FAINT))
    out.append(_rule(style))

    # The two numbers a reader has to see together. "read" on its own invites
    # the conclusion that everything else came back clean.
    out += _rows(
        style,
        [
            ("read", f"{_plural(len(read), 'file')}, {_plural(survey.findings, 'finding')}"),
            ("not read", _plural(len(refused), "file")),
        ],
        width,
    )

    if survey.by_detector:
        out.append("")
        out += _header(style, "what was found", _plural(len(survey.by_detector), "kind"))
        out += _rows(
            style,
            [(kind, _plural(n, "file")) for kind, n in survey.by_detector.items()],
            width,
        )

    if hiding:
        out.append("")
        out += _header(style, "files that hide something", _plural(len(hiding), "file"))
        out += _rows(
            style,
            [(_relative(survey, r), ", ".join(r.detectors)) for r in hiding],
            width,
        )

    if refused:
        out.append("")
        out += _header(style, "not read", _plural(len(refused), "file"))
        out += _rows(
            style,
            [(_relative(survey, r), _reason(r)) for r in refused],
            width,
        )

    out.append("")
    out.append(_rule(style))
    for line in textwrap.wrap(_tail(survey), width=width - len(MARGIN)) or [""]:
        out.append(MARGIN + style.ink(line, MUTED))
    out.append("")
    return "\n".join(out)


def _reason(result) -> str:
    """The refusal, with the file's own name taken off the front of it.

    The readers phrase their refusals as `deck.pptx is a presentation, and...`,
    which reads twice when the name is already the label on the left.
    """
    reason = result.refusal or ""
    prefix = f"{result.path.name} "
    return reason[len(prefix) :] if reason.startswith(prefix) else reason


def _tail(survey: Survey) -> str:
    if not survey.results:
        return "no files to read here."
    if not survey.read:
        return (
            f"none of these {_plural(len(survey.results), 'file')} could be read, "
            "so none of them has been searched."
        )
    detail = "unmasker <file> for the detail, --json for all of it."
    if survey.refused:
        return (
            f"searched {_plural(len(survey.read), 'file')}. "
            f"{_plural(len(survey.refused), 'file')} could not be read and "
            f"{'has' if len(survey.refused) == 1 else 'have'} not been searched. "
            + detail
        )
    return f"searched {_plural(len(survey.read), 'file')}. " + detail


def as_json(survey: Survey) -> dict:
    """The archive half. Every finding in every file, which is what lets the
    screen be a summary rather than a scroll."""
    return {
        "tool": "unmasker",
        "version": __version__,
        "root": str(survey.root),
        "files": [
            {
                "file": str(result.path),
                "kind": result.kind,
                # False for a refused file, and it means *nothing was
                # searched* rather than *nothing was found*.
                "searched": result.searched,
                "refused": result.refusal,
                "remarks": list(result.remarks),
                "findings": [f.as_dict() for f in result.findings],
            }
            for result in survey.results
        ],
    }
