"""The report as Markdown.

Four outputs, four readers. The terminal triages, `--json` is the pipeline's
archive, `--html` is the page you attach to an email, and this is the one that
goes into a wiki, a ticket, a pull request or a notebook - places that already
speak Markdown, where an HTML attachment is the wrong shape.

## Markdown is the more dangerous of the two, not the safer one

An HTML renderer handed `<script>` prints it, because `html.py` escapes it. A
**Markdown** renderer handed `<script>` *runs* it, because passing raw HTML
through is what Markdown does - on GitHub, in a wiki, in every editor preview.

So this is not the HTML rules translated. It is a different set of rules for a
more permissive format, and it has to hold against three kinds of damage, each
of which arrives inside a document written by whoever is being investigated:

- **raw HTML**, which becomes live markup wherever this is rendered
- **`|`**, which silently splits one table cell into two and puts every column
  after it under the wrong heading
- **backticks, asterisks and underscores**, which turn somebody else's text
  into somebody else's formatting

## Three ways in, three treatments

**Quoted evidence goes in a fenced block.** Nothing inside a fence is markup,
so `|`, `*` and `<img>` are all inert - and the fence is grown longer than the
longest run of backticks inside it, because that is the one character that can
break out from within.

**Prose is escaped inline.** A summary is this tool's sentence, but it
interpolates values out of the document, so the specials are backslashed and
`<` becomes an entity.

**Table cells are escaped and the pipe is doubly so.** A row that disagrees
with its header renders as garbage in every viewer, and silently.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import __version__
from .findings import Finding
from .readers import Extraction
from .scan import Survey

#: The characters that mean something to a Markdown parser **in the middle of a
#: sentence**, which is the only place a value is ever put.
#:
#: Deliberately short. `.`, `-`, `#` and `+` matter at the start of a line and
#: nowhere else, and escaping them everywhere turned `bids.xlsx` into
#: `bids\.xlsx` and a path into `pytest\-of\-oryon` - names a reader cannot
#: search the report for, which is the whole reason they are printed.
#:
#: `<` is not here because it is replaced with its entity first: raw HTML is
#: the one that does damage rather than merely looking wrong.
SPECIAL = re.compile(r"([\\`*_\[\]])")


def _inline(text: str) -> str:
    """A value put into a sentence. Escaped, not fenced, because a sentence
    with a code span in the middle of it reads worse than one without."""
    return SPECIAL.sub(r"\\\1", text.replace("<", "&lt;")).replace("\n", " ")


def _cell(text: str) -> str:
    """A value in a table. The pipe is what breaks a row, so it goes first."""
    return _inline(text).replace("|", "\\|")


def _fence(text: str) -> str:
    """Quoted evidence, in a block long enough to contain itself.

    A backtick is the only character that can end a code span from inside one,
    so the fence is one longer than the longest run in the value. Three is the
    floor because a shorter fence is not a fence.
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _finding(finding: Finding) -> list[str]:
    where = str(finding.location)
    out = [
        f"**{_inline(finding.summary)}**  ",
        f"_{_inline(finding.basis.value)} · {_inline(where)}_",
        "",
        "human sees",
        _fence(finding.human_sees) if finding.human_sees.strip() else "_nothing on the page_",
        "",
        "machine reads",
        _fence(finding.machine_reads) if finding.machine_reads.strip() else "_nothing in the file_",
        "",
    ]
    if finding.decoded:
        out += ["decodes to", _fence(finding.decoded), ""]
    return out


def _findings(findings: list[Finding], level: int = 2) -> list[str]:
    by_detector: dict[str, list[Finding]] = {}
    for finding in findings:
        by_detector.setdefault(finding.detector, []).append(finding)

    out: list[str] = []
    for detector, group in by_detector.items():
        out.append(f"{'#' * level} {detector} — {_plural(len(group), 'finding')}")
        out.append("")
        for finding in group:
            out += _finding(finding)
    return out


def _notes(remarks, level: int = 2) -> list[str]:
    if not remarks:
        return []
    return (
        [f"{'#' * level} notes", ""]
        + [f"- {_inline(remark)}" for remark in remarks]
        + [""]
    )


def _searched(extraction: Extraction, findings: list[Finding]) -> str:
    if not extraction.has_text:
        return "This file has no text layer to search, so nothing here has been searched."
    if findings:
        return f"Searched the text of this file. {_plural(len(findings), 'finding')}."
    return "Searched the text of this file. Nothing hidden found by the detectors that exist."


def render_file(path: Path, extraction: Extraction, findings: list[Finding]) -> str:
    count = _plural(len(findings), "finding") if findings else "nothing hidden found"
    lines = [
        f"# unmasker — {_inline(path.name)}",
        "",
        f"`{_inline(str(path))}`",
        "",
        f"{_inline(count)}",
        "",
    ]
    # The path says where; the digest says what. A report is forwarded, and
    # its reader needs to be able to check the file against it.
    if extraction.sha256:
        lines += [f"`sha256 {_inline(extraction.sha256)}`", ""]
    lines += _findings(findings)
    lines += _notes(extraction.remarks)
    lines += ["---", "", _inline(_searched(extraction, findings)), "", f"unmasker {__version__}"]
    return "\n".join(lines) + "\n"


def _relative(survey: Survey, result) -> str:
    try:
        return str(result.path.relative_to(survey.root))
    except ValueError:
        return str(result.path)


def render_survey(survey: Survey) -> str:
    hiding = survey.hiding
    refused = survey.refused

    lines = [
        f"# unmasker — {_inline(survey.root.name or str(survey.root))}",
        "",
        f"`{_inline(str(survey.root))}`",
        "",
        f"{len(hiding)} of {_plural(len(survey.results), 'file')} hide something",
        "",
        "## what was read",
        "",
        f"- read: {_plural(len(survey.read), 'file')}, "
        f"{_plural(survey.findings, 'finding')}",
        f"- not read: {_plural(len(refused), 'file')}",
        "",
    ]

    if survey.by_detector:
        lines += [
            f"## what was found — {_plural(len(survey.by_detector), 'kind')}",
            "",
            "| kind | files |",
            "| --- | --- |",
        ]
        lines += [
            f"| {_cell(kind)} | {_plural(n, 'file')} |" for kind, n in survey.by_detector.items()
        ]
        lines.append("")

    if hiding:
        lines += [
            f"## files that hide something — {_plural(len(hiding), 'file')}",
            "",
            "| file | kinds |",
            "| --- | --- |",
        ]
        lines += [
            f"| {_cell(_relative(survey, r))} | {_cell(', '.join(r.detectors))} |" for r in hiding
        ]
        lines.append("")

    if refused:
        lines += [
            f"## not read — {_plural(len(refused), 'file')}",
            "",
            "| file | why |",
            "| --- | --- |",
        ]
        lines += [
            f"| {_cell(_relative(survey, r))} | {_cell(r.refusal or '')} |" for r in refused
        ]
        lines.append("")

    for result in hiding:
        lines += [
            "---",
            "",
            f"## {_inline(_relative(survey, result))}",
            "",
            f"_{_inline(', '.join(result.detectors))}_",
            "",
        ]
        lines += _findings(list(result.findings), level=3)
        lines += _notes(result.remarks, level=3)

    lines += ["---", "", _inline(_tail(survey)), "", f"unmasker {__version__}"]
    return "\n".join(lines) + "\n"


def _tail(survey: Survey) -> str:
    if not survey.results:
        return "No files to read here."
    if not survey.read:
        return (
            f"None of these {_plural(len(survey.results), 'file')} could be read, "
            "so none of them has been searched."
        )
    tail = f"Searched {_plural(len(survey.read), 'file')}."
    if survey.refused:
        tail += (
            f" {_plural(len(survey.refused), 'file')} could not be read and "
            f"{'has' if len(survey.refused) == 1 else 'have'} not been searched."
        )
    return tail
