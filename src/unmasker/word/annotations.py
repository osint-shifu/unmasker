"""Comments in a .doc, and the name the file puts on each one.

A comment's text is not where its author is. The text sits in the annotation
story, laid end to end with every other comment in the document; the names sit
in a separate table in the `1Table` stream; and a third table says which name
belongs to which comment and where in the document it was anchored. Reading
one without the others gives a comment attributed to nobody, which is half the
evidence - a candid sentence matters most when it has a name on it.

Two things here came out of the bytes rather than the specification.

**`GrpXstAtnOwners` is not a string table.** The name says so - a *group of
Xst* - but it is easy to read as one of the `Sttb` structures beside it and
mis-parse the first name, which is what happened here before the bytes were
dumped: a header that is not there ate the first two characters of *Halina*.

**An `ATRD` of this size carries no date.** The 30-byte form has an owner
index and the author's initials and nothing else. `None` is the answer, and it
is a different answer from a date this reader failed to find.
"""

from __future__ import annotations

import struct

from ..revisions import Comment
from .marks import readable

#: `fcPlcfandRef`, `fcPlcfandTxt` and `fcGrpXstAtnOwners`, as pair numbers in
#: the `FibRgFcLcb` blob that begins at 0x9A.
REFERENCES, TEXTS, OWNERS = 8, 10, 72

#: One `ATRDPre10`: an `Xst` of ten units for the initials, then the owner
#: index, the kind, the bookmark flags and its tag.
ATRD = 30

#: A comment longer than this is not being quoted into a report; it is a
#: document of its own, and the count says so instead.
MAX_COMMENTS = 4096


def _pair(word: bytes, number: int) -> tuple[int, int]:
    """The offset and length stored as pair `number` of the FIB's blob."""
    at = 0x9A + number * 4
    if at + 8 > len(word):
        return 0, 0
    return struct.unpack_from("<II", word, at)


def _owners(table: bytes, start: int, length: int) -> list[str]:
    """Every name in `GrpXstAtnOwners`, in the order the index counts them.

    A bare run of `Xst`: a count of characters, then that many UTF-16 units,
    then the next one. No header, whatever the neighbouring structures do.
    """
    if not length or start + length > len(table):
        return []
    blob = table[start : start + length]
    names, at = [], 0
    while at + 2 <= len(blob):
        count, = struct.unpack_from("<H", blob, at)
        at += 2
        if count == 0 or at + count * 2 > len(blob):
            break
        names.append(blob[at : at + count * 2].decode("utf-16-le", "replace"))
        at += count * 2
    return names


def read_comments(
    word: bytes, table: bytes, story: str
) -> tuple[tuple[Comment, ...], list[str]]:
    """The document's comments, with a name on each where the file gives one.

    `story` is the annotation story: every comment's text, end to end. Where
    the tables that carve it up cannot be read, the whole story is returned as
    one comment rather than dropped - the words are in the file either way,
    and losing them to a table this reader could not parse would be the tool
    failing to report what it had already decoded.
    """
    if not story.strip():
        return (), []

    reference_at, reference_size = _pair(word, REFERENCES)
    text_at, text_size = _pair(word, TEXTS)
    owner_at, owner_size = _pair(word, OWNERS)

    names = _owners(table, owner_at, owner_size)
    count = (reference_size - 4) // (4 + ATRD) if reference_size > 4 else 0

    unparsed = [
        Comment(text=readable(story).strip(), author=None, date=None)
    ], [
        "this file's comments could not be split into separate ones, so they "
        "are reported together and without the names attached to them"
    ]

    if count < 1 or count > MAX_COMMENTS:
        return tuple(unparsed[0]), unparsed[1]
    if reference_at + reference_size > len(table) or text_at + text_size > len(table):
        return tuple(unparsed[0]), unparsed[1]

    references = table[reference_at : reference_at + reference_size]
    boundaries = table[text_at : text_at + text_size]
    if text_size < (count + 1) * 4:
        return tuple(unparsed[0]), unparsed[1]

    positions = struct.unpack_from(f"<{count + 1}I", boundaries, 0)
    descriptors = 4 * (count + 1)

    comments: list[Comment] = []
    for index in range(count):
        entry = descriptors + index * ATRD
        initials_length, = struct.unpack_from("<H", references, entry)
        owner, = struct.unpack_from("<H", references, entry + 20)
        initials = ""
        if 0 < initials_length <= 9:
            initials = references[
                entry + 2 : entry + 2 + initials_length * 2
            ].decode("utf-16-le", "replace")

        text = readable(story[positions[index] : positions[index + 1]]).strip()
        if not text:
            continue
        comments.append(
            Comment(
                text=text,
                author=names[owner] if owner < len(names) else None,
                # The 30-byte form holds no date. Nothing was found because
                # there is nothing there, which is not the same as a date this
                # reader could not read.
                date=None,
                initials=initials or None,
            )
        )

    if not comments:
        return tuple(unparsed[0]), unparsed[1]
    return tuple(comments), []


__all__ = ["read_comments"]
