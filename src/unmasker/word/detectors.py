"""What a Word document holds and does not draw.

One finding, and it is not a new kind of statement. Word's hidden attribute
and a PDF render mode that paints neither fill nor stroke say the same thing
about a document: **these characters are in the file and not on the page.** So
this produces `invisible-text`, the name the PDF detector already uses, rather
than a second name for one idea - a reader who has learned what the finding
means in one container should not have to learn it again in another.

Tracked changes are not here. A deletion is `deleted-text` and belongs with
every other deletion this tool reports, in `unmasker.revisions`, which is
where the DOCX and OpenDocument readers already send theirs.

Field instructions are not here either, and that is a decision rather than an
omission. Every table of contents, page number and cross-reference in every
document ever written is a field; making each one a finding would fire on
almost every real .doc, which is the `filetrail` failure of a score that was
high on everything and therefore said nothing. They are stated as a remark,
and the ones naming a location - a URL, a path - are quoted there in full.
"""

from __future__ import annotations

from ..findings import Basis, Finding, Location


def _count(text: str) -> str:
    return f"{len(text)} character" + ("" if len(text) == 1 else "s")


def hidden_text(record) -> list[Finding]:
    """Runs carrying Word's hidden attribute."""
    findings = []
    for run in record.hidden:
        where = "" if run.name == "the document" else f", in {run.name}"
        findings.append(
            Finding(
                detector="invisible-text",
                basis=Basis.DIRECT,
                summary=(
                    f"{_count(run.text)} carry Word's hidden attribute{where}, "
                    "which the application does not draw and no print of this "
                    "document would show; the characters are in the file"
                ),
                human_sees="",
                machine_reads=run.text,
                location=Location(),
            )
        )
    return findings


def detect(record) -> list[Finding]:
    """Every finding this reader can make about a Word document's own text."""
    return hidden_text(record)


__all__ = ["detect", "hidden_text"]
