"""The property set: a compound file's account of itself.

Where OOXML writes `<dc:creator>` and a PDF writes `/Author`, a compound file
writes a **serialised property set** - a numbered table with its own code page,
its own string type and its own epoch. The names in this module are the
numbering, and they are the only reason the values mean anything.

Two things here came from reading a real file rather than the specification,
and both would have been wrong the other way round.

The code page is declared by the file, in property 1, and LibreOffice writes
65001. Assuming the usual CP1252 returns the right answer for plain ASCII and
mangles every name with a diacritic in it, which is most names this tool exists
to report.

A `FILETIME` of zero is not a moment in 1601. It is a field nobody filled in,
and this omits it, because printing an epoch would be inventing evidence out of
an absence - the same distinction the rest of the tool keeps between *searched
and empty* and *nothing to search*.
"""

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

#: The two sets Office writes, keyed by the FMTID as it is stored - a GUID
#: with its first three fields little-endian, which is why these look scrambled
#: beside the numbers in the specification.
SUMMARY = bytes.fromhex("e0859ff2f94f6810ab9108002b27b3d9")
DOCUMENT_SUMMARY = bytes.fromhex("02d5cdd59c2e1b10939708002b2cf9ae")

#: The user-defined section, which sits beside DocumentSummaryInformation in
#: the same stream and numbers nothing: its names are in a dictionary under
#: property 0. LibreOffice puts a document's Company field here rather than in
#: the standard property the specification names for it, which is the sort of
#: disagreement between a format and its producers that only a real file shows.
USER_DEFINED = bytes.fromhex("05d5cdd59c2e1b10939708002b2cf9ae")

NAMES: dict[bytes, dict[int, str]] = {
    SUMMARY: {
        2: "Title",
        3: "Subject",
        4: "Author",
        5: "Keywords",
        6: "Comments",
        7: "Template",
        8: "Last Saved By",
        9: "Revision Number",
        10: "Total Editing Time",
        11: "Last Printed",
        12: "Create Time",
        13: "Last Saved Time",
        14: "Page Count",
        15: "Word Count",
        16: "Character Count",
        18: "Application Name",
    },
    DOCUMENT_SUMMARY: {
        2: "Category",
        3: "Presentation Format",
        6: "Slide Count",
        8: "Paragraph Count",
        9: "Line Count",
        14: "Manager",
        15: "Company",
    },
}

#: Between the FILETIME epoch and the Unix one.
EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

VT_I2, VT_I4, VT_LPSTR, VT_FILETIME = 2, 3, 30, 64

#: A property set claiming more than this is damaged or hostile. The number is
#: far above anything Office writes and far below anything that costs time.
MAX_PROPERTIES = 4096


def _codepage(number: int) -> str:
    """The Python codec for a Windows code page number."""
    if number == 65001:
        return "utf-8"
    if number < 0:
        number += 1 << 16
    return f"cp{number}"


def _time(value: int) -> str | None:
    """A FILETIME as an ISO timestamp, or None where nobody set one."""
    if value <= 0:
        return None
    try:
        return (EPOCH + timedelta(microseconds=value // 10)).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _value(blob: bytes, at: int, encoding: str) -> str | None:
    if at + 4 > len(blob):
        return None
    kind = struct.unpack("<I", blob[at : at + 4])[0]
    body = at + 4

    if kind == VT_LPSTR:
        if body + 4 > len(blob):
            return None
        length = struct.unpack("<I", blob[body : body + 4])[0]
        raw = blob[body + 4 : body + 4 + max(0, length)]
        return raw.split(b"\x00", 1)[0].decode(encoding, "replace") or None
    if kind == VT_I4 and body + 4 <= len(blob):
        return str(struct.unpack("<i", blob[body : body + 4])[0])
    if kind == VT_I2 and body + 2 <= len(blob):
        return str(struct.unpack("<h", blob[body : body + 2])[0])
    if kind == VT_FILETIME and body + 8 <= len(blob):
        return _time(struct.unpack("<Q", blob[body : body + 8])[0])
    return None


def _dictionary(blob: bytes, at: int, encoding: str) -> dict[int, str]:
    """The name each numbered property goes by in a user-defined section.

    Property 0 carries no type tag: its value begins with the entry count, and
    each entry is an id, a length, and a NUL-terminated name. The length counts
    characters for a UTF-16 code page and bytes for every other, which is why
    the encoding has to be known before this is read.
    """
    names: dict[int, str] = {}
    if at + 4 > len(blob):
        return names

    count = struct.unpack("<I", blob[at : at + 4])[0]
    cursor = at + 4
    wide = encoding in ("utf-16-le", "utf-16")

    for _ in range(min(count, MAX_PROPERTIES)):
        if cursor + 8 > len(blob):
            break
        pid, length = struct.unpack("<II", blob[cursor : cursor + 8])
        cursor += 8
        span = length * 2 if wide else length
        raw = blob[cursor : cursor + span]
        cursor += span + (span % 4 and 4 - span % 4 if wide else 0)
        name = raw.split(b"\x00", 1)[0].decode(encoding, "replace")
        if name:
            names[pid] = name
    return names


def read_properties(blob: bytes) -> dict[str, str]:
    """Every named property in a property-set stream.

    Damage is silence rather than an exception: this reads a stream out of a
    file somebody else wrote, and a metadata table that will not parse is a
    thing the report can say nothing about, not a reason to abandon the file.
    """
    if len(blob) < 48 or blob[:2] != b"\xfe\xff":
        return {}

    try:
        sections = struct.unpack("<I", blob[24:28])[0]
        found: dict[str, str] = {}

        for index in range(min(sections, 8)):
            head = 28 + index * 20
            fmtid, offset = struct.unpack("<16sI", blob[head : head + 20])
            names = NAMES.get(fmtid)
            if (names is None and fmtid != USER_DEFINED) or offset + 8 > len(blob):
                continue

            count = struct.unpack("<I", blob[offset + 4 : offset + 8])[0]
            table = [
                struct.unpack("<II", blob[offset + 8 + n * 8 : offset + 16 + n * 8])
                for n in range(min(count, MAX_PROPERTIES))
                if offset + 16 + n * 8 <= len(blob)
            ]

            # The code page has to be read before anything is decoded with it,
            # and it is simply another numbered property in the same table.
            page = next((v for pid, v in table if pid == 1), None)
            encoding = "cp1252"
            if page is not None:
                declared = _value(blob, offset + page, "ascii")
                if declared is not None:
                    encoding = _codepage(int(declared))

            if names is None:
                # A user-defined section: the names are in the file, not here.
                names = _dictionary(blob, offset + dict(table)[0], encoding) if any(
                    pid == 0 for pid, _ in table
                ) else {}

            for pid, at in table:
                name = names.get(pid)
                if name is None:
                    continue
                value = _value(blob, offset + at, encoding)
                if value:
                    found[name] = value
        return found
    except (struct.error, ValueError, LookupError):
        return {}


__all__ = ["read_properties", "SUMMARY", "DOCUMENT_SUMMARY", "USER_DEFINED", "NAMES"]
