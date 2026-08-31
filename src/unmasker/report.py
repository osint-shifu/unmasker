"""The terminal report.

The layout is `filetrail`'s, described in `/data/filetrail/DESIGN.md`, because
`CLAUDE.md` says to read that before inventing a second design language. What
carries over:

- **No boxes.** A frame costs two columns on every line it wraps, and nothing
  in a forensic report needs to be in one. Grouping is a one-character gutter.
- **Nothing is truncated.** A value too long for the line wraps. An ellipsis
  sends the reader to fetch the value another way, which defeats having read
  the report.
- **Section headers only when there is more than one section.** A file whose
  findings are all of one kind gets no headers; the grouping would be noise.
- **A column is sized per section, not once per screen.** One global width
  makes a layout look *almost* aligned, which reads worse than not aligning.

What is new here is the shape of an entry. `filetrail` answers "where did this
come from"; unmasker answers "what does this look like, against what does it
say", so every entry is two readings and the gap between them.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from .findings import Basis, Finding
from .readers import Extraction
from .theme import FAINT, FOREGROUND, GLYPHS, INK, MUTED, Depth, Ink, glyphs, paint

MARGIN = "  "
LEFT = len(MARGIN) + 2  # margin, gutter glyph, space


@dataclass
class Style:
    depth: Depth = Depth.NONE
    width: int = 78
    glyph: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.glyph is None:
            self.glyph = {name: rich for name, (rich, _) in GLYPHS.items()}

    def ink(self, text: str, ink: Ink, *, bold: bool = False) -> str:
        return paint(text, ink, self.depth, bold=bold)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _rule(style: Style) -> str:
    return MARGIN + style.ink(style.glyph["rule"] * (style.width - len(MARGIN)), FAINT)


def _header(style: Style, left: str, right: str) -> list[str]:
    """A section header: lowercase name at the left, its count at the right.

    Lowercase on purpose. Capitals read as chrome, and this report has none.
    """
    pad = max(1, style.width - len(MARGIN) - len(left) - len(right))
    return [
        MARGIN + style.ink(left, MUTED) + " " * pad + style.ink(right, FAINT),
        _rule(style),
    ]


def _field(style: Style, label: str, value: str, label_width: int) -> list[str]:
    """One labelled reading, wrapped rather than cut.

    The continuation indent lands under the value, so a wrapped reading still
    reads as one value and not as a new field.
    """
    gutter = style.ink(style.glyph["pipe"], FAINT)
    indent = LEFT + label_width + 2
    room = max(20, style.width - indent)

    if not value:
        # An empty reading is a statement, not a gap in the output: for
        # white-on-white text a human sees nothing at all, and a blank column
        # reads as a rendering fault rather than as the finding.
        return [
            MARGIN
            + gutter
            + " "
            + style.ink(label.ljust(label_width), FAINT)
            + "  "
            + style.ink("nothing on the page", FAINT)
        ]

    lines = textwrap.wrap(
        value,
        width=room,
        break_long_words=True,
        break_on_hyphens=False,
        drop_whitespace=True,
    ) or [""]

    out = [
        MARGIN
        + gutter
        + " "
        + style.ink(label.ljust(label_width), FAINT)
        + "  "
        + style.ink(lines[0], FOREGROUND)
    ]
    for extra in lines[1:]:
        out.append(
            MARGIN + gutter + " " * (indent - len(MARGIN) - 1) + style.ink(extra, FOREGROUND)
        )
    return out


def _entry(style: Style, finding: Finding, label_width: int) -> list[str]:
    ink = INK[finding.basis]
    where = str(finding.location)

    summary = finding.summary
    room = style.width - LEFT - len(where) - 2
    if len(summary) > room:
        # The summary wraps too; the location stays on the first line, where a
        # reader scanning the right-hand edge expects it.
        head, *rest = textwrap.wrap(summary, width=max(20, room)) or [""]
    else:
        head, rest = summary, []

    pad = max(1, style.width - LEFT - len(head) - len(where))
    lines = [
        MARGIN
        + style.ink(style.glyph["bullet"], ink)
        + " "
        + style.ink(head, ink)
        + " " * pad
        + style.ink(where, FAINT)
    ]
    for extra in rest:
        lines.append(MARGIN + " " * 2 + style.ink(extra, ink))

    lines += _field(style, "human sees", finding.human_sees, label_width)
    lines += _field(style, "machine reads", finding.machine_reads, label_width)
    if finding.decoded:
        lines += _field(style, "decodes to", finding.decoded, label_width)
    return lines


def _searched(extraction: Extraction) -> str:
    """What was actually looked at. Never a claim that outruns the reading."""
    if not extraction.has_text:
        return "nothing to search: this file yielded no text"
    pages = [u.page for u in extraction.units if u.page is not None]
    with_text = [u for u in extraction.units if u.text.strip()]
    if pages:
        return f"searched {_plural(len(with_text), 'page')} of {len(pages)}"
    return "searched the text of this file"


def render(
    path: str,
    extraction: Extraction,
    findings: list[Finding],
    style: Style | None = None,
) -> str:
    style = style or Style()
    out: list[str] = [""]

    # The masthead must not contradict the footer. A file with no text layer
    # was not searched, and saying "nothing hidden found" about it is the
    # confusion CLAUDE.md names: searched-and-empty is not nothing-to-search.
    if findings:
        count = _plural(len(findings), "finding")
    elif extraction.has_text:
        count = "nothing hidden found"
    else:
        count = "nothing to search"
    name = style.ink("unmasker", FOREGROUND, bold=True)
    room = style.width - len(MARGIN) - len("unmasker") - 2 - len(count) - 1
    if len(path) <= room:
        pad = style.width - len(MARGIN) - len("unmasker") - 2 - len(path) - len(count)
        out.append(
            MARGIN + name + "  " + style.ink(path, FAINT) + " " * pad + style.ink(count, MUTED)
        )
    else:
        # A path too long to share the line gets its own, wrapped. The count
        # stays where a reader scanning the right-hand edge expects it, and the
        # masthead never runs past the width it declared.
        pad = style.width - len(MARGIN) - len("unmasker") - len(count)
        out.append(MARGIN + name + " " * pad + style.ink(count, MUTED))
        for line in textwrap.wrap(path, width=style.width - LEFT) or [path]:
            out.append(MARGIN + "  " + style.ink(line, FAINT))
    out.append(_rule(style))

    by_detector: dict[str, list[Finding]] = {}
    for f in findings:
        by_detector.setdefault(f.detector, []).append(f)

    for detector, group in by_detector.items():
        out.append("")
        if len(by_detector) > 1:
            out += _header(style, detector, _plural(len(group), "finding"))
        # Per section, not once per screen: a section with no decoded value
        # must not carry the width of one that has.
        labels = ["human sees", "machine reads"]
        if any(f.decoded for f in group):
            labels.append("decodes to")
        width = max(len(x) for x in labels)
        for f in group:
            out += _entry(style, f, width)
            out.append("")
        if out[-1] == "":
            out.pop()

    if extraction.remarks:
        out.append("")
        out += _header(style, "notes", _plural(len(extraction.remarks), "note"))
        for remark in extraction.remarks:
            for line in textwrap.wrap(remark, width=style.width - LEFT) or [""]:
                out.append(MARGIN + "  " + style.ink(line, FAINT))

    out.append("")
    out.append(_rule(style))
    tail = _searched(extraction)
    if findings:
        kinds = _plural(len(by_detector), "kind")
        tail += f". {_plural(len(findings), 'finding')} in {kinds}"
    elif extraction.has_text:
        tail += ". Nothing hidden found by the detectors that exist"
    out.append(MARGIN + style.ink(tail + ".", MUTED))
    out.append("")
    return "\n".join(out)


def basis_key(finding: Finding) -> str:
    """The word the report uses for `how we know`. Never a number."""
    return finding.basis.value


__all__ = ["Style", "render", "basis_key", "Basis", "glyphs"]
