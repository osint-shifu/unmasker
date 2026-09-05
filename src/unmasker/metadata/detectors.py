"""Findings from metadata: the part of it the document does not show.

Most metadata is not a finding, and getting that wrong would cost more than
missing it. Every PDF carries a Producer and every .docx an Application; if
those produced findings the tool would exit non-zero on every document ever
written, and the exit code - which is the whole CI gate,
in place of a `--strict` mode - would stop meaning anything.

So the tool fields, the counts and the ordinary dates are remarks. What becomes
a finding is the gap:

**`undisclosed-metadata`** — a value a person put in a content field that the
document itself never shows. A briefing whose visible text is anonymous and
whose `/Author` names someone is the whole of why this detector exists; it is
how leaked documents get attributed.

**`metadata-path`** — an absolute path. It leaks a directory structure, a
username and often a client name, all from one string, so it gets its own line
rather than being one more undisclosed value.

**`metadata-conflict`** — the file contradicting itself. A PDF states its
metadata twice, in the Info dictionary and in an XMP packet, and nothing makes
the two agree; tools that "remove metadata" routinely clear one and leave the
other. Two timestamps in the wrong order are the same kind of statement. Both
are one question - *which of these does the file mean?* - so both are one
detector.

**`revision-history`** — the `xmpMM:History` trail: which applications have
touched the file, and when. One finding for the file, the same rule the DOCX
tracked-change history follows, arriving in a different container.

Everything here is `SELF_REPORTED`. That is what the class is for: a name in a
document is whatever the application that wrote it was configured to say - Word,
LibreOffice and every other editor take it from a preference somebody typed once
- and the report says so rather than treating it as identification.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..findings import Basis, Finding, Location
from . import Metadata

# What an absolute path looks like, and nothing else does. Deliberately narrow:
# `24.2.7.2` and `LibreOffice/24.2.7.2$Linux_X86_64` must not match, and a
# pattern loose enough to catch a relative path would catch both.
PATH = re.compile(
    r"""^(?:
        /[^/\s][^\s]*          # /home/someone/file
      | [A-Za-z]:[\\/][^\s]*   # C:\Users\someone\file
      | \\\\[^\\\s]+\\[^\s]*   # \\server\share\file
    )$""",
    re.VERBOSE,
)

# Below this, a value would turn up inside an unrelated document by chance, and
# a finding suppressed by chance is worse than one never made.
SHORTEST_MATCH = 4


def _shown(value: str, text: str) -> bool:
    """Whether the document itself shows this value.

    If it does there is no gap, and no finding: a title printed on the page is
    not something hidden in the file.
    """
    if len(value.strip()) < SHORTEST_MATCH:
        return False
    return value.strip().lower() in (text or "").lower()


def _timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _significance(name: str) -> str:
    """What a field means, where the name alone would not tell a reader.

    A UUID reported as "a value the document does not show" is true and flat.
    `xmpMM:OriginalDocumentID` is the file recording that it came from another
    document, which is a different sentence and a far more useful one - and it
    is the same principle as everywhere else here: the name of a field is
    evidence, so use it.
    """
    lowered = name.lower()
    if "originaldocumentid" in lowered:
        return (
            "; this identifier names the document this one was made from, and "
            "survives across saves that change everything else"
        )
    if "derivedfrom" in lowered:
        return "; this identifier names a document this one was derived from"
    return ""


def undisclosed(metadata: Metadata, text: str) -> list[Finding]:
    """Content-field values the document never shows."""
    findings = []
    for entry in metadata.by_role("content"):
        value = entry.value.strip()
        if not value or PATH.match(value) or _shown(value, text):
            continue
        findings.append(
            Finding(
                detector="undisclosed-metadata",
                basis=Basis.SELF_REPORTED,
                summary=(
                    f"the {entry.name} field of {entry.part} holds a value the "
                    "document does not show anywhere in its text" + _significance(entry.name)
                ),
                human_sees="",
                machine_reads=value,
                location=Location(),
            )
        )
    return findings


def paths(metadata: Metadata, text: str) -> list[Finding]:
    """Absolute paths, wherever in the metadata they turn up."""
    findings = []
    for entry in metadata.fields:
        value = entry.value.strip()
        if entry.role == "tool" or not PATH.match(value):
            continue
        findings.append(
            Finding(
                detector="metadata-path",
                basis=Basis.SELF_REPORTED,
                summary=(
                    f"the {entry.name} field of {entry.part} holds a filesystem "
                    "path, which names a directory structure and usually an "
                    "account as well"
                ),
                human_sees="",
                machine_reads=value,
                location=Location(),
            )
        )
    return findings


def conflicts(metadata: Metadata, text: str) -> list[Finding]:
    """Timestamps in the file that contradict one another.

    A file modified before it was created is not impossible to explain - a
    clock, a timezone, a copy - but the file is stating two things that cannot
    both be plain fact, and which of them to believe is the reader's to decide.
    """
    stamps = {
        entry.name.lower(): (entry, _timestamp(entry.value)) for entry in metadata.by_role("time")
    }
    findings = []
    for created_name, modified_name in (("creationdate", "moddate"), ("created", "modified")):
        created = stamps.get(created_name)
        modified = stamps.get(modified_name)
        if not created or not modified or created[1] is None or modified[1] is None:
            continue
        if modified[1] >= created[1]:
            continue
        findings.append(
            Finding(
                detector="metadata-conflict",
                basis=Basis.SELF_REPORTED,
                summary=(
                    f"the file says it was modified at {modified[0].value} and "
                    f"created at {created[0].value}, which is the wrong way "
                    "round; a clock, a timezone or a copy can do this, and so "
                    "can an edited timestamp"
                ),
                human_sees="",
                machine_reads=f"{modified[0].name} {modified[0].value}",
                location=Location(),
            )
        )
    return findings


# What the Info dictionary calls a thing, against what XMP calls it. Taken from
# the PDF specification's XMP mapping and not from the names: `/Subject` maps
# onto `dc:description`, while `dc:subject` is `/Keywords`. Pairing these by
# name would compare two fields that mean different things and report a
# conflict that is not one.
EQUIVALENT = (
    ("Author", "dc:creator"),
    ("Title", "dc:title"),
    ("Subject", "dc:description"),
    ("Keywords", "pdf:Keywords"),
    ("CreationDate", "xmp:CreateDate"),
    ("ModDate", "xmp:ModifyDate"),
    # Listed so the tool-role guard below has something to guard. These two
    # disagree in enormous numbers of ordinary files - a PDF written by one
    # application and distilled by another says both, truthfully - and a
    # detector that fired on them would bury the pairs that matter.
    ("Creator", "xmp:CreatorTool"),
    ("Producer", "pdf:Producer"),
)


def disagreements(metadata: Metadata, text: str) -> list[Finding]:
    """The Info dictionary and the XMP packet stating different things.

    Only where *both* say something. XMP holding an author the Info dictionary
    lacks is XMP holding more, not the file contradicting itself, and that is
    already `undisclosed-metadata`.

    Tool fields are left out. `/Creator` and `xmp:CreatorTool` disagree in
    enormous numbers of perfectly ordinary files, and a detector that fired on
    those would drown the one that matters.
    """
    findings = []
    for info_name, xmp_name in EQUIVALENT:
        here = metadata.where(info_name, "/Info")
        there = metadata.where(xmp_name, "XMP")
        if here is None or there is None:
            continue
        if here.role == "tool" or there.role == "tool":
            continue
        if here.value.strip() == there.value.strip():
            continue
        findings.append(
            Finding(
                detector="metadata-conflict",
                basis=Basis.SELF_REPORTED,
                summary=(
                    f"the Info dictionary gives {info_name} as "
                    f'"{here.value}" and the XMP packet gives {xmp_name} as '
                    f'"{there.value}". A PDF states its metadata twice and '
                    "nothing makes the two agree; a tool that clears one and "
                    "not the other leaves exactly this"
                ),
                human_sees="",
                machine_reads=there.value,
                location=Location(),
            )
        )
    return findings


def revision_history(metadata: Metadata, text: str) -> list[Finding]:
    """The XMP edit trail: what has touched this file, and when."""
    if not metadata.history:
        return []
    events = [event.described() for event in metadata.history]
    tools = [event.software for event in metadata.history if event.software]
    return [
        Finding(
            detector="revision-history",
            basis=Basis.SELF_REPORTED,
            summary=(
                f"the XMP packet records {len(events)} event"
                f"{'' if len(events) == 1 else 's'} in this file's history: "
                + "; ".join(events)
                + ". It is the file's own account, and it outlives the "
                + (
                    "Info dictionary, which is where anybody checking will look"
                    if metadata.container == "pdf"
                    else "other places this file states things about itself"
                )
            ),
            human_sees="",
            machine_reads=", ".join(dict.fromkeys(tools)) or "; ".join(events),
            location=Location(),
        )
    ]


def describe(metadata: Metadata) -> list[str]:
    """One remark saying what the file claims produced it, and when.

    A remark rather than a finding, on purpose. This is true of every document
    and reporting it would make the exit code useless.
    """
    if not metadata.fields:
        return []
    parts = []
    tools = [f"{e.name} {e.value}" for e in metadata.by_role("tool")]
    if tools:
        parts.append("says it was made by " + "; ".join(tools))
    times = [f"{e.name} {e.value}" for e in metadata.by_role("time")]
    if times:
        parts.append("dates itself " + "; ".join(times))
    counts = [f"{e.name} {e.value}" for e in metadata.by_role("count")]
    if counts:
        parts.append("counts " + "; ".join(counts))
    if not parts:
        return []
    return [f"the file {', and '.join(parts)}"]


def detect(metadata: Metadata, text: str, *, comparable: bool = True) -> list[Finding]:
    """Every metadata finding, given what the document itself shows.

    `text` is the document's own text, and it is what makes these findings
    about a *gap* rather than a dump of the Info dictionary.

    `comparable` is false where the document has text that was not read. Then
    there is no gap to report - not because the value is shown, but because
    nothing looked - and `undisclosed` is skipped rather than firing on every
    field. The remaining detectors do not compare against the text and are
    unaffected.
    """
    return (
        (undisclosed(metadata, text) if comparable else [])
        + paths(metadata, text)
        + conflicts(metadata, text)
        + disagreements(metadata, text)
        + revision_history(metadata, text)
    )
