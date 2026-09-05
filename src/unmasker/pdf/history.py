"""Earlier revisions of a PDF, which the file still holds.

A PDF is appended to rather than rewritten. An edit leaves the original bytes
where they are and writes a new cross-reference section after them, ending in a
second `%%EOF`. Every earlier revision of the document is therefore still in
the file, and a page removed that way has not gone anywhere - the new catalogue
stops pointing at it, every viewer stops drawing it, and the text is untouched.

It is the cleanest failed redaction there is: nothing was covered, nothing was
made invisible, the content was simply unreferenced. It is also invisible to
any tool that reads only what the current catalogue points at, which is most of
them, including the rest of this one.

**Boundaries are found in the raw bytes and then proved by parsing.** `%%EOF`
can occur inside a stream, so an offset is a candidate and nothing more; a
candidate becomes a revision only when the bytes before it parse as a complete
document on their own. That is slower than trusting the marker and it is the
reason a false positive here is close to impossible.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from ..findings import Basis, Finding, Location

MARKER = b"%%EOF"

#: How many candidate boundaries are examined. Each costs a parse of the file
#: up to that point, and a document with more revisions than this is rare
#: enough that saying so beats spending the time. Exceeding it is remarked on
#: rather than passed over.
LIMIT = 8


@dataclass(frozen=True)
class Revision:
    """One earlier state of the document, and what it said."""

    number: int
    """1-based, counting from the first revision written."""

    ends_at: int
    """Byte offset just past this revision's `%%EOF`."""

    pages: int
    text: str


def _candidates(data: bytes) -> list[int]:
    offsets, at = [], 0
    while (found := data.find(MARKER, at)) != -1:
        offsets.append(found + len(MARKER))
        at = found + len(MARKER)
    return offsets


def revisions(data: bytes) -> tuple[list[Revision], list[str]]:
    """Every earlier revision in `data`, and anything worth remarking on.

    The last boundary is the document as it stands and is not returned: it is
    not an earlier revision, it is this one.
    """
    from pypdf import PdfReader

    offsets = _candidates(data)
    remarks: list[str] = []
    if len(offsets) < 2:
        return [], remarks

    earlier = offsets[:-1]
    if len(earlier) > LIMIT:
        remarks.append(
            f"this file holds {len(earlier)} earlier revisions and the first "
            f"{LIMIT} were read; the rest were not searched"
        )
        earlier = earlier[:LIMIT]

    found: list[Revision] = []
    for at in earlier:
        try:
            reader = PdfReader(io.BytesIO(data[:at]))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            pages = len(reader.pages)
        except Exception:
            # Not a revision boundary: a `%%EOF` inside a stream, or a
            # revision this parser cannot read. Either way there is nothing to
            # report about it, and guessing would be worse than silence.
            continue
        found.append(Revision(number=len(found) + 1, ends_at=at, pages=pages, text=text))

    return found, remarks


def _lines(text: str) -> list[str]:
    """Non-empty lines, whitespace collapsed.

    Two extractions of the same page differ in spacing often enough that
    comparing them raw would report a difference nobody made.
    """
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def detect(earlier: tuple, shown: str) -> list[Finding]:
    """What an earlier revision holds that the document no longer shows.

    A count of revisions is trivia. The finding is the text: a line that was in
    the file before the edit, is in the file now, and is on none of the pages
    a reader is given.

    Reported per revision rather than merged, because two edits are two
    statements about what somebody decided to stop showing, and merging them
    would rank one against the other - which is the mistake this project's
    notes name first.
    """
    current = set(_lines(shown))
    total = len(earlier) + 1

    findings = []
    for revision in earlier:
        dropped = [line for line in _lines(revision.text) if line not in current]
        if not dropped:
            continue
        findings.append(
            Finding(
                detector="earlier-revision",
                basis=Basis.DIRECT,
                summary=(
                    f"this file holds {total} revisions of itself, and revision "
                    f"{revision.number} - {revision.pages} page"
                    f"{'' if revision.pages == 1 else 's'}, ending at byte "
                    f"{revision.ends_at} - still holds text no page shows now. "
                    "A PDF is appended to rather than rewritten, so an edit "
                    "leaves what it replaced in the file"
                ),
                human_sees="",
                machine_reads="\n".join(dropped),
                location=Location(),
            )
        )
    return findings


__all__ = ["Revision", "revisions", "detect", "LIMIT"]
