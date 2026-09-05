"""Which characters are deleted, and which are hidden. Nothing else says.

A .doc keeps the text of a tracked deletion **in the piece table, beside the
text that is printed**, and so does a run somebody marked hidden. Neither is
drawn. Nothing about the characters themselves distinguishes them, so a reader
that stops at the piece table hands on a deleted sentence as text a person can
see - and hands on Word's hidden text as ordinary prose, which is the exact
statement this tool exists to contradict.

What distinguishes them is a `Chpx`: a short list of properties, stored in a
512-byte page, reached through `PlcfBteChpx`, and addressed by **byte offset
into the stream rather than by character position**. So the pieces have to be
mapped back onto it, which is the awkward part of this module and the reason
it takes a piece layout rather than a string.

Every sprm here was read out of the specimens before this module existed, and
one of them corrected a wrong memory: `0x0800` is the **delete** mark and
`0x0801` the insert, not the other way round. Guessing that pair the wrong way
round would have produced a tool that took insertions off the page and
reported deletions as visible text - wrong in both directions at once, and
green against any fixture built from the same wrong memory.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

#: `PlcfBteChpx` and `SttbfRMark`, as pair numbers in the FIB blob at 0x9A.
CHARACTER_BINS, AUTHORS = 24, 102

#: An FKP page is this many bytes, and the last of them is the run count.
PAGE = 512

#: The properties this reads. A `Chpx` holds dozens; these four are the ones
#: that decide whether a character is on the page and who put it there.
DELETED, INSERTED, HIDDEN = 0x0800, 0x0801, 0x083C
AUTHOR_OF = {0x4863: "deletion", 0x4804: "insertion"}
DATE_OF = {0x6864: "deletion", 0x6805: "insertion"}

#: How many bytes each kind of sprm operand takes, by its `spra` - the top
#: three bits of the sprm. 6 is variable and handled where it is read.
OPERAND = {0: 1, 1: 1, 2: 2, 3: 4, 4: 2, 5: 2, 7: 3}

#: A document with more property pages than this is past what this tool is
#: meant for, and the cap is what stops a corrupt table spinning.
MAX_PAGES = 1 << 16


class UnreadableProperties(Exception):
    """The tables that say which characters are on the page could not be read.

    Raised rather than answered with "none deleted". Those are different
    findings: one is *searched, and there are none*, the other is *nothing
    looked*, and handing back the second dressed as the first is the mistake
    this whole tool is built to prevent.
    """


@dataclass(frozen=True)
class Run:
    """One stretch of the stream, and what its properties say about it."""

    start: int
    """First byte of the run in the WordDocument stream."""

    end: int
    """One past its last byte."""

    deleted: bool = False
    inserted: bool = False
    hidden: bool = False
    author: str | None = None
    date: str | None = None

    @property
    def off_the_page(self) -> bool:
        """Whether a person reading the document would see these characters.

        An insertion is not here. It is text somebody added and everybody can
        read; filtering it out with the deletions would take words off a page
        they are on.
        """
        return self.deleted or self.hidden


def _sttb(table: bytes, start: int, length: int) -> list[str]:
    """An extended string table: `0xFFFF`, a count, an extra width, the names.

    The opposite shape from `GrpXstAtnOwners`, two structures away in the same
    stream, which is a bare run of counted strings with no header at all. Both
    were read out of the bytes; neither was assumed from the other.
    """
    if not length or start < 0 or start + length > len(table):
        return []
    blob = table[start : start + length]
    if len(blob) < 6:
        return []
    marker, count, extra = struct.unpack_from("<HHH", blob, 0)
    if marker != 0xFFFF:
        return []
    names, at = [], 6
    for _ in range(count):
        if at + 2 > len(blob):
            break
        size, = struct.unpack_from("<H", blob, at)
        at += 2
        if at + size * 2 > len(blob):
            break
        names.append(blob[at : at + size * 2].decode("utf-16-le", "replace"))
        at += size * 2 + extra
    return names


def _when(packed: int) -> str | None:
    """A `DTTM` as an ISO timestamp, or None where the file states no date.

    The layout was worked out against two dates this repository's specimen
    builder wrote, rather than taken from memory, and it is reported as `None`
    rather than as a guess where the fields do not make a date. A wrong
    timestamp in a report is worse than an absent one: somebody would act on
    it.
    """
    minute = packed & 0x3F
    hour = (packed >> 6) & 0x1F
    day = (packed >> 11) & 0x1F
    month = (packed >> 16) & 0x0F
    year = 1900 + ((packed >> 20) & 0x1FF)
    if not (1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


def _properties(grpprl: bytes) -> dict:
    """The four properties this reads, out of one run's property list.

    Walking it means knowing every sprm's operand width, because they are laid
    end to end with nothing between them. Where a width cannot be worked out
    the walk stops rather than carrying on at an offset that is now wrong -
    what has been read stays read, and what has not is not invented.
    """
    found: dict = {}
    at = 0
    while at + 2 <= len(grpprl):
        sprm, = struct.unpack_from("<H", grpprl, at)
        at += 2
        size = OPERAND.get(sprm >> 13)
        if size is None:  # variable: the operand says how long it is
            if at >= len(grpprl):
                break
            size = 1 + grpprl[at]
        if at + size > len(grpprl):
            break
        operand = grpprl[at : at + size]
        at += size

        if sprm == DELETED:
            found["deleted"] = operand[0] != 0
        elif sprm == INSERTED:
            found["inserted"] = operand[0] != 0
        elif sprm == HIDDEN:
            found["hidden"] = operand[0] != 0
        elif sprm in AUTHOR_OF:
            found["author_index"] = int.from_bytes(operand[:2], "little")
        elif sprm in DATE_OF:
            found["date"] = _when(int.from_bytes(operand[:4], "little"))
    return found


def _page(word: bytes, number: int, names: list[str]) -> list[Run]:
    """One FKP page: the runs it covers, and what each one's properties say."""
    start = number * PAGE
    if start < 0 or start + PAGE > len(word):
        raise UnreadableProperties(
            f"a property page at byte {start} is past the end of a "
            f"{len(word)}-byte stream"
        )
    page = word[start : start + PAGE]
    count = page[PAGE - 1]
    if count == 0 or 4 * (count + 1) + count > PAGE - 1:
        raise UnreadableProperties(f"a property page claims {count} runs")

    boundaries = struct.unpack_from(f"<{count + 1}I", page, 0)
    offsets = page[4 * (count + 1) : 4 * (count + 1) + count]

    runs = []
    for index in range(count):
        if boundaries[index + 1] < boundaries[index]:
            raise UnreadableProperties("a property run ends before it begins")
        found: dict = {}
        if offsets[index]:
            at = offsets[index] * 2
            if at < PAGE:
                size = page[at]
                found = _properties(page[at + 1 : at + 1 + size])
        who = found.get("author_index")
        runs.append(
            Run(
                start=boundaries[index],
                end=boundaries[index + 1],
                deleted=bool(found.get("deleted")),
                inserted=bool(found.get("inserted")),
                hidden=bool(found.get("hidden")),
                author=names[who] if who is not None and who < len(names) else None,
                date=found.get("date"),
            )
        )
    return runs


def read_runs(word: bytes, table: bytes) -> tuple[Run, ...]:
    """Every run in the document, with the properties that decide what shows.

    An empty result where the file holds no property table is the true answer:
    a document with no `Chpx` has nothing deleted and nothing hidden. A table
    that is there and cannot be read raises instead, because those two are not
    the same finding.
    """
    at = 0x9A + CHARACTER_BINS * 4
    if at + 8 > len(word):
        raise UnreadableProperties("the header is too short to name a property table")
    start, length = struct.unpack_from("<II", word, at)
    if length == 0:
        return ()
    if length < 12 or start < 0 or start + length > len(table):
        raise UnreadableProperties(
            f"the property table is given as bytes {start}-{start + length} of a "
            f"{len(table)}-byte stream"
        )

    count = (length - 4) // 8
    if count < 1 or count > MAX_PAGES:
        raise UnreadableProperties(f"a property table of {count} pages is not readable")

    author_at, author_length = struct.unpack_from("<II", word, 0x9A + AUTHORS * 4)
    names = _sttb(table, author_at, author_length)

    pages = struct.unpack_from(f"<{count}I", table, start + 4 * (count + 1))
    runs: list[Run] = []
    for page in pages:
        runs.extend(_page(word, page & 0x3FFFFF, names))
    return tuple(sorted(runs, key=lambda run: run.start))


__all__ = ["Run", "UnreadableProperties", "read_runs"]
