"""Findings from a Word document's tracked changes and comments.

Three, and the split between them is the point.

**`deleted-text`** — one per deletion. The words are in the file and not on the
page, which is the same statement this tool makes about a black bar and about a
zero-width character. The author and the date go in the summary, because a
deletion without them is half the evidence.

**`comment`** — one per comment. A comment is not part of the document a reader
prints, and it is very often where the candid sentence lives.

**`revision-history`** — exactly one, for the whole file. Who edited a document
and when is *one fact about the document*, not one fact per change. A draft
with two hundred insertions must not produce two hundred findings; that is the
`filetrail` lesson about a report nobody finishes reading, arriving from a new
direction. It is `SELF_REPORTED`, which is what that class was defined for: the
file's own account of itself, believed only as far as a file can be. An author
name in a .docx is whatever the copy of Word was configured to say.
"""

from __future__ import annotations

from ..findings import Basis, Finding, Location
from .revisions import RevisionRecord


def _count(text: str) -> str:
    """`1 character`, not `1 characters`. A report is read by a person."""
    return f"{len(text)} character" + ("" if len(text) == 1 else "s")


def _attribution(author: str | None, date: str | None) -> str:
    who = author or "an author the file does not state"
    when = f" on {date}" if date else ", at a time the file does not state"
    return f"{who}{when}"


def deleted_text(record: RevisionRecord) -> list[Finding]:
    """Text a tracked change took off the page and left in the file."""
    findings = []
    for revision in record.revisions:
        if not revision.hides_text:
            continue
        where = "" if revision.part == "word/document.xml" else f", in {revision.part}"
        kind = "deleted" if revision.kind == "deletion" else "moved away"
        findings.append(
            Finding(
                detector="deleted-text",
                basis=Basis.DIRECT,
                summary=(
                    f"{_count(revision.text)} {kind} by "
                    f"{_attribution(revision.author, revision.date)}{where}; the "
                    "text is still in the file"
                ),
                human_sees="",
                machine_reads=revision.text,
                location=Location(),
            )
        )
    return findings


def comments(record: RevisionRecord) -> list[Finding]:
    """Comment text, which is in the file and not in the document."""
    return [
        Finding(
            detector="comment",
            basis=Basis.DIRECT,
            summary=(
                f"a comment by {_attribution(comment.author, comment.date)}, "
                "carried in the file and not part of the document body"
            ),
            human_sees="",
            machine_reads=comment.text,
            location=Location(),
        )
        for comment in record.comments
        if comment.text.strip()
    ]


def revision_history(record: RevisionRecord) -> list[Finding]:
    """One finding for the whole file: who worked on it, and between when."""
    if record.is_empty:
        return []
    authors = record.authors
    if not authors:
        return []

    counts: dict[str, int] = {}
    for revision in record.revisions:
        counts[revision.kind] = counts.get(revision.kind, 0) + 1
    if record.comments:
        counts["comment"] = len(record.comments)
    tally = ", ".join(
        f"{n} {kind}" if n == 1 else f"{n} {kind}s" for kind, n in sorted(counts.items())
    )

    dates = record.dates
    when = ""
    if len(dates) == 1:
        when = f", on {dates[0]}"
    elif dates:
        when = f", between {dates[0]} and {dates[-1]}"

    people = "1 person" if len(authors) == 1 else f"{len(authors)} people"
    return [
        Finding(
            detector="revision-history",
            basis=Basis.SELF_REPORTED,
            summary=(
                f"the file records {tally}, by {people}{when}. A name here is "
                "whatever the copy of Word was configured to say"
            ),
            human_sees="",
            machine_reads=", ".join(authors),
            location=Location(),
        )
    ]


def detect(record: RevisionRecord) -> list[Finding]:
    """Every tracked-change finding in one document.

    Additive, and none outranks another: a file can hide a sentence in a
    deletion *and* carry a candid comment *and* name three editors, and those
    are three findings.
    """
    return deleted_text(record) + comments(record) + revision_history(record)
