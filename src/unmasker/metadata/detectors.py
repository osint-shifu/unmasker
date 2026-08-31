"""Findings from metadata: the part of it the document does not show.

Most metadata is not a finding, and getting that wrong would cost more than
missing it. Every PDF carries a Producer and every .docx an Application; if
those produced findings the tool would exit non-zero on every document ever
written, and the exit code - which `HANDOFF.md` records as the whole CI gate,
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

**`metadata-conflict`** — the file contradicting itself about its own dates.

Everything here is `SELF_REPORTED`. That is what the class is for: a name in a
.docx is whatever that copy of Word was configured to say, and the report says
so rather than treating it as identification.
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
                    "document does not show anywhere in its text"
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


def detect(metadata: Metadata, text: str) -> list[Finding]:
    """Every metadata finding, given what the document itself shows.

    `text` is the document's own text, and it is what makes these findings
    about a *gap* rather than a dump of the Info dictionary.
    """
    return undisclosed(metadata, text) + paths(metadata, text) + conflicts(metadata, text)
