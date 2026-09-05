"""Whole files carried inside other files.

A PDF holds them in `/Names/EmbeddedFiles`; an OOXML package holds them as
archive members. Either way they are on no page, no viewer shows one without
being asked, and printing the document does not print it. The attachment
travels with the file and appears nowhere in it.

**This is not a redaction failure and must never be reported as one.** An
attachment is a feature and is used deliberately all the time - an invoice with
its structured data, a report with the workbook behind it. The finding is that
one is there and the page does not say so. What it means is the reader's to
decide, which is the same posture as every other detector here.

The basis is DIRECT: the bytes were read out of the file, not inferred from it.
"""

from __future__ import annotations

from .findings import Basis, Finding, Location


def _size(count: int) -> str:
    """Bytes, stated as bytes. A file of 1.2 KB is a file of 1231 bytes, and
    rounding it loses the only number a reader could check."""
    return f"{count} byte" + ("" if count == 1 else "s")


def detect_attachments(attachments: tuple) -> list[Finding]:
    findings = []
    for carried in attachments:
        # Naming the same string twice - `"Object 1/" in Object 1/` - teaches a
        # reader that the second half of a sentence carries nothing.
        where = (
            f" in {carried.part}"
            if carried.part and carried.part.rstrip("/") != carried.name.rstrip("/")
            else ""
        )
        attached = carried.part.startswith("/Names")
        quoted = carried.text
        findings.append(
            Finding(
                detector="attached-file",
                basis=Basis.DIRECT,
                summary=(
                    f'this document carries a file called "{carried.name}"'
                    f"{where}, {_size(carried.size)} of it, "
                    + (
                        "which is on no page and does not print with the document"
                        if attached
                        # An embedded object is on the page. The picture of it
                        # is; saying otherwise would overstate the finding.
                        else "of which the page shows a rendering rather than "
                        "the file itself"
                    )
                ),
                # An attachment is on no page; an embedded object is, as a
                # picture. Saying "nothing on the page" about the second would
                # contradict the sentence above it.
                human_sees="" if attached else "a rendering of it",
                # "Nothing in the file" is the wrong answer about a file that
                # is plainly there. Where the content cannot be shown, what it
                # is can be.
                machine_reads=quoted if quoted is not None else carried.description,
                location=Location(),
            )
        )
    return findings


__all__ = ["detect_attachments"]
