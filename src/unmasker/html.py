"""The report as a file somebody can send.

Three outputs, three readers. The terminal report triages, `--json` is the
archive a pipeline reads, and this is the archive a **person** reads - the one
that gets attached to an email and opened by a lawyer, an editor or a clerk who
has nothing installed and no reason to trust the attachment.

That audience decides everything here.

**One file, nothing loaded from anywhere.** No stylesheet link, no font, no
image, no script. It has to open offline, from a mail client, on a machine
nobody prepared.

**No JavaScript at all**, not even for something convenient. An attachment that
asks a law office to run code is an attachment that gets deleted, and rightly.

**The full detail, not the summary.** The terminal survey triages because a
folder of two hundred files printed in full is a scroll nobody reads. A browser
has search, anchors and a scrollbar, so this is where the whole record goes -
and the overview at the top links into it.

**Built for paper.** It ends up in a case file, which means printed, which
means page breaks between documents and ink that survives being black and
white.

## Escaping is the feature, not the hygiene

`SECURITY.md` says this tool parses hostile files by design, and every string
it quotes came out of a document somebody else wrote. A PDF whose `Producer`
field reads `<img src=x onerror=...>` would otherwise put a live handler into
the report *of that PDF*, in the browser of the person investigating it.

So everything that reaches the page goes through `escape`, and a test asserts
there is no `<script`, no `javascript:` and no inline event handler anywhere in
the output. There is exactly one place in this module where a string is
interpolated without escaping, and it is the CSS, which comes from here.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from . import __version__
from .findings import Basis, Finding
from .readers import Extraction
from .scan import Survey

#: The three evidence classes, in the hues `theme.py` gives them. Colour
#: encodes how the tool knows and never how bad the finding is, so these are
#: three neighbours rather than a traffic light - and the word is printed
#: beside the swatch, because a reader who prints this in black and white must
#: lose nothing.
INK = {
    Basis.DIRECT: "#2f6b4f",
    Basis.CIRCUMSTANTIAL: "#7f5c0d",
    Basis.SELF_REPORTED: "#365b82",
}

STYLE = """
:root {
  --paper: #ffffff; --ink: #14171a; --muted: #5c6367; --faint: #8b9296;
  --rule: #e2e5e8; --quiet: #f6f7f8;
  --direct: #2f6b4f; --circumstantial: #7f5c0d; --self-reported: #365b82;
}
* { box-sizing: border-box; }
/* Prose about the evidence is set proportionally; the evidence itself stays
   monospace. A path, a quoted value, a codepoint and a detector slug are all
   things a reader compares character by character, and a document that set
   them in a proportional face would be asking them not to. */
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 15.5px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
        Helvetica, Arial, sans-serif;
}
code, .mono, .mark, .subject, .rows .k, .rows .slugs, .reading dd, .kinds,
.file h3, .head h2 {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
main { max-width: 54rem; margin: 0 auto; padding: 3rem 1.5rem 5rem; }
h1, h2, h3 { font-weight: 600; margin: 0; }
a { color: inherit; }

.mark { font-size: 1.6rem; line-height: 1.15; letter-spacing: -0.02em; }
.mark .bar { background: var(--ink); color: var(--ink); }
.mark .under { color: var(--muted); }
.subject { color: var(--faint); word-break: break-all; margin-top: .75rem; }
.tally { color: var(--muted); margin-top: .35rem; }

section { margin-top: 2.75rem; }
.head {
  display: flex; justify-content: space-between; gap: 1rem;
  align-items: baseline; border-bottom: 1px solid var(--rule);
  padding-bottom: .4rem; margin-bottom: 1.1rem;
}
.head h2 { font-size: 1.02rem; }
.head .count { color: var(--faint); white-space: nowrap; }

.finding { margin: 0 0 1.6rem; }
.claim { display: flex; gap: .55rem; align-items: baseline; }
.dot { width: .5rem; height: .5rem; border-radius: 50%; flex: none; margin-top: .45rem; }
.where { color: var(--faint); white-space: nowrap; margin-left: auto; }
.basis { font-size: .8rem; color: var(--faint); }

.reading { display: grid; grid-template-columns: 8.5rem 1fr; gap: .3rem .9rem;
           margin: .6rem 0 0 1.05rem; }
.reading dt { color: var(--faint); }
.reading dd { margin: 0; white-space: pre-wrap; word-break: break-word; }
.reading dd.absent { color: var(--faint); font-style: italic; }

.rows { display: grid; grid-template-columns: auto 1fr; gap: .3rem 1rem; }
.rows .k { color: var(--ink); white-space: nowrap; }
.rows .v { color: var(--muted); word-break: break-word; }

.notes { color: var(--muted); }
.notes li { margin-bottom: .35rem; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--rule);
         color: var(--muted); }

.file { margin-top: 2.5rem; padding-top: 1.25rem; border-top: 2px solid var(--rule); }
.file h3 { word-break: break-all; }
.file .kinds { color: var(--faint); margin-top: .2rem; }

@media print {
  body { font-size: 10.5pt; }
  main { padding: 0; max-width: none; }
  .file { break-before: page; }
  .finding, .reading { break-inside: avoid; }
  a { text-decoration: none; }
}
"""


def _mark() -> str:
    """The bar, and the word it failed to cover. Spans rather than an image,
    so it survives being printed and copied."""
    return (
        '<div class="mark"><span class="bar">█████</span>ker<br>'
        '<span class="under">unmasker</span></div>'
    )


def _document(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n<main>\n{body}\n</main>\n"
        "</body>\n</html>\n"
    )


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _head(name: str, count: str) -> str:
    return (
        f'<div class="head"><h2>{escape(name)}</h2>'
        f'<span class="count">{escape(count)}</span></div>'
    )


def _reading(label: str, value: str, absent: str) -> str:
    if value.strip():
        return f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>"
    return f'<dt>{escape(label)}</dt><dd class="absent">{escape(absent)}</dd>'


def _finding(finding: Finding) -> str:
    where = str(finding.location)
    rows = [
        _reading("human sees", finding.human_sees, "nothing on the page"),
        _reading("machine reads", finding.machine_reads, "nothing in the file"),
    ]
    if finding.decoded:
        rows.append(_reading("decodes to", finding.decoded, ""))

    return (
        '<div class="finding">'
        f'<div class="claim"><span class="dot" style="background:{INK[finding.basis]}"></span>'
        f"<span>{escape(finding.summary)}</span>"
        f'<span class="where">{escape(where)}</span></div>'
        f'<div class="basis" style="margin-left:1.05rem">{escape(finding.basis.value)}</div>'
        f'<dl class="reading">{"".join(rows)}</dl>'
        "</div>"
    )


def _findings(findings: list[Finding]) -> str:
    by_detector: dict[str, list[Finding]] = {}
    for finding in findings:
        by_detector.setdefault(finding.detector, []).append(finding)

    out = []
    for detector, group in by_detector.items():
        out.append("<section>")
        out.append(_head(detector, _plural(len(group), "finding")))
        out.extend(_finding(f) for f in group)
        out.append("</section>")
    return "".join(out)


def _notes(remarks) -> str:
    if not remarks:
        return ""
    items = "".join(f"<li>{escape(remark)}</li>" for remark in remarks)
    return (
        "<section>"
        + _head("notes", _plural(len(remarks), "note"))
        + f'<ul class="notes">{items}</ul></section>'
    )


def _searched(extraction: Extraction, findings: list[Finding]) -> str:
    """Never a claim that outruns the reading - the same sentence the terminal
    footer prints, for the same reason."""
    if not extraction.has_text:
        return "This file has no text layer to search, so nothing here has been searched."
    if findings:
        return f"Searched the text of this file. {_plural(len(findings), 'finding')}."
    return "Searched the text of this file. Nothing hidden found by the detectors that exist."


def render_file(path: Path, extraction: Extraction, findings: list[Finding]) -> str:
    name = str(path)
    count = _plural(len(findings), "finding") if findings else "nothing hidden found"
    body = (
        f'<header>{_mark()}'
        f'<div class="subject">{escape(name)}</div>'
        f'<div class="tally">{escape(count)}</div></header>'
        + _findings(findings)
        + _notes(extraction.remarks)
        + f"<footer>{escape(_searched(extraction, findings))}<br>"
        + f"unmasker {escape(__version__)}</footer>"
    )
    return _document(f"unmasker — {path.name}", body)


def _anchor(index: int) -> str:
    """Positional, not derived from the path: a file name is attacker-supplied
    and an id built out of one is a way into the document's own markup."""
    return f"f{index}"


def render_survey(survey: Survey) -> str:
    hiding = survey.hiding
    refused = survey.refused

    order = {id(result): i for i, result in enumerate(survey.results)}

    overview = [
        f'<header>{_mark()}'
        f'<div class="subject">{escape(str(survey.root))}</div>'
        f'<div class="tally">'
        f"{len(hiding)} of {escape(_plural(len(survey.results), 'file'))} hide something"
        "</div></header>"
    ]

    overview.append("<section>")
    overview.append(_head("what was read", ""))
    overview.append(
        '<div class="rows">'
        f'<span class="k">read</span><span class="v">'
        f"{escape(_plural(len(survey.read), 'file'))}, "
        f"{escape(_plural(survey.findings, 'finding'))}</span>"
        f'<span class="k">not read</span><span class="v">'
        f"{escape(_plural(len(refused), 'file'))}</span>"
        "</div></section>"
    )

    if survey.by_detector:
        rows = "".join(
            f'<span class="k">{escape(kind)}</span>'
            f'<span class="v">{escape(_plural(n, "file"))}</span>'
            for kind, n in survey.by_detector.items()
        )
        overview.append(
            "<section>"
            + _head("what was found", _plural(len(survey.by_detector), "kind"))
            + f'<div class="rows">{rows}</div></section>'
        )

    if hiding:
        rows = "".join(
            f'<span class="k"><a href="#{_anchor(order[id(r)])}">'
            f"{escape(_relative(survey, r))}</a></span>"
            f'<span class="v slugs">{escape(", ".join(r.detectors))}</span>'
            for r in hiding
        )
        overview.append(
            "<section>"
            + _head("files that hide something", _plural(len(hiding), "file"))
            + f'<div class="rows">{rows}</div></section>'
        )

    if refused:
        rows = "".join(
            f'<span class="k">{escape(_relative(survey, r))}</span>'
            f'<span class="v">{escape(r.refusal or "")}</span>'
            for r in refused
        )
        overview.append(
            "<section>"
            + _head("not read", _plural(len(refused), "file"))
            + f'<div class="rows">{rows}</div></section>'
        )

    detail = []
    for result in hiding:
        detail.append(
            f'<div class="file" id="{_anchor(order[id(result)])}">'
            f"<h3>{escape(_relative(survey, result))}</h3>"
            f'<div class="kinds">{escape(", ".join(result.detectors))}</div>'
            + _findings(list(result.findings))
            + _notes(result.remarks)
            + "</div>"
        )

    body = "".join(overview) + "".join(detail) + f"<footer>{escape(_tail(survey))}</footer>"
    return _document(f"unmasker — {survey.root.name or survey.root}", body)


def _relative(survey: Survey, result) -> str:
    try:
        return str(result.path.relative_to(survey.root))
    except ValueError:
        return str(result.path)


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
    return tail + f" unmasker {__version__}"
