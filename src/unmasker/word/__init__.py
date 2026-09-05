"""The `WordDocument` stream: where a .doc keeps its text, and in what shape.

A .doc does not store its text as a run of characters you can find and decode.
It stores a **piece table**: a list saying that characters 0 to 68 live at one
offset in one encoding, 68 to 460 at another offset in another. Word wrote it
that way so a save could append rather than rewrite, and the consequence is
that the text of a document is scattered through the stream in the order it was
edited, not the order it is read.

Three things here came out of real LibreOffice output rather than out of the
specification, and each of them is a way this reader would otherwise have been
quietly wrong.

**The main story is not the document.** All of a file's text shares one
character-position space, and the FIB says how much of it belongs to what:
`ccpText`, then footnotes, headers and footers, comments, endnotes, text boxes.
In the stories specimen the main story is 267 characters of 504. A reader that
took `[0, ccpText)` would search just over half the file and then report having
searched it - and the part it skipped holds the comment naming a bidder and the
header marked *internal circulation only*. That is `filetrail`'s HEIC failure
arriving in a new format: a reader correct against the specification, decoding
nothing that matters from anything real.

**A hyperlink is a field, not a run.** The bytes hold
`0x13 HYPERLINK "https://..." 0x14 published summary 0x15` - an instruction, a
separator, a result. The page shows the result. Concatenating the characters
would put a URL into the visible text, and every detector downstream would then
be working from a page nobody can see. So the two are separated here, and the
instruction is kept rather than dropped: it is the whole reason a forensic tool
opens the file.

**The text is UTF-16 even when it is all ASCII.** The specification presents
the compressed 8-bit piece first and LibreOffice never writes one, so a reader
built in the order the specification reads gets the rarer case tested and the
common one guessed at.

What this does not read is character formatting. Hidden text - Word's
`fHidden` run property - is a `Chpx` in a different table and is named in the
specimen notes as the next thing rather than passed over in silence.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..revisions import Comment, Revision
from .annotations import read_comments
from .marks import readable
from .properties import Run, UnreadableProperties, read_runs

#: What a Word 97 stream begins with. `0xA5DC` is Word 6 and 95, which this
#: refuses rather than reads: their FIB has no `FibRgFcLcb97`, so the offset
#: below lands in the middle of something else and would yield text made out
#: of unrelated bytes.
IDENT = 0xA5EC

#: The oldest FIB this reader understands. LibreOffice's "Word 97" export
#: writes 257, not 193 - a version check for equality would refuse the only
#: producer on this machine.
OLDEST = 193

FENCRYPTED = 0x0100
FWHICHTBLSTM = 0x0200

#: Where `fcClx`/`lcbClx` sit: 66 pairs into the `FibRgFcLcb` blob, which
#: begins at 0x9A in every version this reader accepts.
CLX = 0x9A + 66 * 4

#: `FibRgLw97` begins here, and the story lengths are the fourth value on.
LW = 0x40

#: The stories, in the order their characters are laid out. `ccpMcr` is
#: between headers and comments, is always zero, and is skipped by name rather
#: than by arithmetic so the order stays legible.
STORIES = (
    ("the document", 3),
    ("footnotes", 4),
    ("headers and footers", 5),
    ("comments", 7),
    ("endnotes", 8),
    ("text boxes", 9),
    ("text boxes in headers and footers", 10),
)

FIELD_BEGIN, FIELD_SEPARATOR, FIELD_END = "\x13", "\x14", "\x15"

#: How many pieces to follow before giving up. A document long enough to need
#: more than this is longer than anything this tool is meant for, and the cap
#: is what stops a corrupt table spinning.
MAX_PIECES = 1 << 16


class NotAWordDocument(ValueError):
    """The stream is not a Word document this reader can read.

    Raised rather than guessed at. A reader that carries on past a header it
    does not understand produces text out of unrelated bytes, which is the one
    thing this tool must never do.
    """


def _eight_bit() -> tuple[str, ...]:
    """The 8-bit piece's character table.

    Windows-1252, except that five of its positions are undefined and the
    Word format uses them for the code points they name. Decoding with the
    codec alone raises on a file that is not wrong.
    """
    table = []
    for code in range(256):
        try:
            table.append(bytes([code]).decode("cp1252"))
        except UnicodeDecodeError:
            table.append(chr(code))
    return tuple(table)


EIGHT_BIT = _eight_bit()


@dataclass(frozen=True)
class Story:
    """One run of text, named the way a person would name where it is."""

    name: str
    text: str


@dataclass(frozen=True)
class FieldCode:
    """A field: what the file computes, and what the page shows for it.

    `instruction` is never on the page. A `HYPERLINK` field's instruction is
    the URL and its result is the words somebody clicks, and the gap between
    those two is what this tool exists to report.
    """

    instruction: str
    result: str


@dataclass(frozen=True)
class WordText:
    stories: tuple[Story, ...] = ()
    """Every story a reader of the printed document could see. Comments are
    not among them: putting one here would have it searched as visible text
    and then reported as something the document shows."""

    comments: tuple[Comment, ...] = ()

    revisions: tuple[Revision, ...] = ()
    """Tracked changes. A deletion's text is in the piece table beside the text
    that is printed, so it has to be taken out of the visible stories and
    reported as what it is."""

    hidden: tuple[Story, ...] = ()
    """Runs carrying Word's hidden attribute: characters in the file that the
    application does not draw. The same statement a PDF makes with a render
    mode that paints neither fill nor stroke."""

    fields: tuple[FieldCode, ...] = ()

    properties_unread: bool = False
    """The tables saying which characters are on the page could not be read.

    Not the same as a document with nothing deleted and nothing hidden. With
    this set the text must not be handed on as though all of it were visible,
    because nothing established that it is."""

    encrypted: bool = False
    """The text is encrypted and was not read. Not the same as a document
    with no text, and the remark says which."""

    remarks: tuple[str, ...] = ()


def _at(blob: bytes, offset: int, size: int, what: str) -> bytes:
    """`size` bytes from `offset`, or a refusal naming what was being read."""
    if offset < 0 or size < 0 or offset + size > len(blob):
        raise NotAWordDocument(
            f"{what} points at bytes {offset}-{offset + size} of a stream "
            f"{len(blob)} bytes long"
        )
    return blob[offset : offset + size]


def _piece_table(table: bytes, start: int, length: int) -> tuple[tuple[int, ...], bytes]:
    """The character positions and the piece descriptors, out of the `Clx`.

    The Clx is a run of formatting groups followed by the one structure that
    matters here. Walking past the groups rather than assuming the table is
    first is not defensive coding: a document that has been edited has them.
    """
    clx = _at(table, start, length, "the piece table")
    at = 0
    while at < len(clx):
        kind = clx[at]
        if kind == 0x01:  # a group of run properties, skipped by its length
            size = int.from_bytes(_at(clx, at + 1, 2, "a property group"), "little")
            at += 3 + size
            continue
        if kind != 0x02:
            raise NotAWordDocument(f"the piece table holds an unknown entry {kind:#04x}")

        size = int.from_bytes(_at(clx, at + 1, 4, "the piece list"), "little")
        pieces = _at(clx, at + 5, size, "the piece list")
        count = (len(pieces) - 4) // 12
        if count < 1 or count > MAX_PIECES:
            raise NotAWordDocument(f"a piece list of {count} pieces is not readable")
        positions = struct.unpack_from(f"<{count + 1}I", pieces, 0)
        return positions, pieces[4 * (count + 1) :]

    raise NotAWordDocument("the piece table holds no list of pieces")


@dataclass(frozen=True)
class Piece:
    """One run of characters, and the bytes it was decoded from.

    Kept because the character properties are addressed by **byte offset**
    while everything else here counts characters, and the two only meet
    through this.
    """

    position: int
    count: int
    offset: int
    width: int


def _text_of(
    word: bytes, positions: tuple[int, ...], descriptors: bytes
) -> tuple[str, tuple[Piece, ...]]:
    """Every piece, decoded and laid end to end in reading order."""
    out: list[str] = []
    pieces: list[Piece] = []
    for index in range(len(positions) - 1):
        _, location, _ = struct.unpack_from("<HIH", descriptors, index * 8)
        characters = positions[index + 1] - positions[index]
        if characters < 0:
            raise NotAWordDocument("a piece runs backwards")

        compressed = bool(location & 0x40000000)
        offset = (location & 0x3FFFFFFF) >> 1 if compressed else location & 0x3FFFFFFF
        width = 1 if compressed else 2
        raw = _at(word, offset, characters * width, "a piece")
        out.append(
            "".join(EIGHT_BIT[byte] for byte in raw) if compressed
            else raw.decode("utf-16-le", "replace")
        )
        pieces.append(
            Piece(position=positions[index], count=characters, offset=offset, width=width)
        )
    return "".join(out), tuple(pieces)


def _spans(
    pieces: tuple[Piece, ...], runs: tuple[Run, ...], length: int
) -> tuple[tuple[int, int, Run | None], ...]:
    """The character space, cut where the properties change.

    The properties are stored against byte offsets and the text is counted in
    characters, so each piece is the ruler that converts one to the other. A
    stretch no run covers comes back with `None`, which is a document with no
    properties there rather than a gap this could not read - `read_runs`
    raises for that case instead.
    """
    cut: list[tuple[int, int, Run]] = []
    for piece in pieces:
        last = piece.offset + piece.count * piece.width
        for run in runs:
            low, high = max(run.start, piece.offset), min(run.end, last)
            if low >= high:
                continue
            cut.append(
                (
                    piece.position + (low - piece.offset) // piece.width,
                    piece.position + (high - piece.offset) // piece.width,
                    run,
                )
            )

    cut.sort(key=lambda span: span[0])
    whole: list[tuple[int, int, Run | None]] = []
    at = 0
    for start, end, run in cut:
        if start > at:
            whole.append((at, start, None))
        if end > at:
            whole.append((max(at, start), end, run))
            at = end
    if at < length:
        whole.append((at, length, None))
    return tuple(whole)


def _split_fields(raw: str) -> tuple[str, tuple[FieldCode, ...]]:
    """Separate what a field computes from what it puts on the page.

    Fields nest - a hyperlink inside a table of contents entry - so this keeps
    a stack rather than scanning for the next separator. A field left open at
    the end of the text is closed here rather than discarded, because half a
    field is still evidence of what the file holds.
    """
    visible: list[str] = []
    fields: list[FieldCode] = []
    stack: list[list] = []

    def emit(text: str) -> None:
        if stack:
            stack[-1][0 if stack[-1][2] else 1] += text
        else:
            visible.append(text)

    for character in raw:
        if character == FIELD_BEGIN:
            stack.append(["", "", True])
        elif character == FIELD_SEPARATOR and stack:
            stack[-1][2] = False
        elif character == FIELD_END and stack:
            instruction, result, _ = stack.pop()
            fields.append(FieldCode(instruction=readable(instruction).strip(), result=result))
            emit(result)
        else:
            emit(character)

    while stack:
        instruction, result, _ = stack.pop()
        fields.append(FieldCode(instruction=readable(instruction).strip(), result=result))
        emit(result)

    return "".join(visible), tuple(fields)


@dataclass(frozen=True)
class _Marked:
    """One stretch of text the properties say is not ordinary body text."""

    part: str
    text: str
    run: Run


def _same(one: Run, two: Run) -> bool:
    """Whether two runs say the same thing about their characters."""
    return (
        one.deleted == two.deleted
        and one.inserted == two.inserted
        and one.hidden == two.hidden
        and one.author == two.author
        and one.date == two.date
    )


def _merged(marked: list[tuple[int, int, Run]]) -> list[tuple[int, int, Run]]:
    """Adjacent stretches saying the same thing, joined into one.

    A hidden phrase with a bold word inside it is three runs in the property
    table and one hidden phrase on the page. Reporting it as three findings is
    the `filetrail` lesson about one hidden line arriving as eight, reached
    from a new direction - and a reader who is given three has to work out for
    themselves that they are one.
    """
    joined: list[tuple[int, int, Run]] = []
    for start, end, run in marked:
        if joined and joined[-1][1] == start and _same(joined[-1][2], run):
            joined[-1] = (joined[-1][0], end, joined[-1][2])
            continue
        joined.append((start, end, run))
    return joined


def read_word(compound) -> WordText:
    """The text of a Word 97 document, story by story.

    `compound` is anything answering `names` and `read` - the compound file
    the document arrived in.
    """
    try:
        word = compound.read("WordDocument")
    except KeyError as exc:
        raise NotAWordDocument("there is no WordDocument stream") from exc

    if len(word) < CLX + 8:
        raise NotAWordDocument("the WordDocument stream is too short to hold a header")

    ident, version = struct.unpack_from("<HH", word, 0)
    if ident != IDENT:
        raise NotAWordDocument(
            f"the WordDocument stream begins {ident:#06x} rather than {IDENT:#06x}"
        )
    if version < OLDEST:
        raise NotAWordDocument(
            f"this file states version {version}; Word 6 and 95 lay their header "
            "out differently, and reading it at these offsets would produce text "
            "out of unrelated bytes"
        )

    flags, = struct.unpack_from("<H", word, 10)
    if flags & FENCRYPTED:
        return WordText(
            encrypted=True,
            remarks=(
                "this document's text is encrypted, so none of it was read - "
                "which is not the same as a document whose text holds nothing",
            ),
        )

    name = "1Table" if flags & FWHICHTBLSTM else "0Table"
    if name not in compound.names:
        raise NotAWordDocument(f"the header names {name}, and there is no such stream")
    table = compound.read(name)

    start, length = struct.unpack_from("<II", word, CLX)
    positions, descriptors = _piece_table(table, start, length)
    whole, pieces = _text_of(word, positions, descriptors)

    remarks: list[str] = []
    unread = False
    try:
        runs = read_runs(word, table)
    except UnreadableProperties as exc:
        # Not "nothing is deleted". Nothing looked, and the difference is the
        # whole reason this tool exists: with the properties unread, the text
        # cannot be handed on as though all of it were on the page.
        runs, unread = (), True
        remarks.append(
            f"the tables saying which of this file's characters are on the page "
            f"could not be read ({exc}), so its text was not searched - a "
            "deletion or a hidden run would be indistinguishable from ordinary "
            "text here"
        )

    spans = _spans(pieces, runs, len(whole))

    lengths = struct.unpack_from("<11I", word, LW)
    stories: list[Story] = []
    hidden: list[_Marked] = []
    revisions: list[_Marked] = []
    fields: list[FieldCode] = []
    annotations = ""
    at = 0
    for label, index in STORIES:
        size = lengths[index]
        if not size:
            continue
        first, last = at, at + size
        at = last
        if label == "comments":
            annotations = whole[first:last]
            continue

        shown: list[str] = []
        marked: list[tuple[int, int, Run]] = []
        for start_at, end_at, run in spans:
            low, high = max(start_at, first), min(end_at, last)
            if low >= high:
                continue
            if run is None or not run.off_the_page:
                shown.append(whole[low:high])
            if run is not None and (run.hidden or run.deleted or run.inserted):
                marked.append((low, high, run))

        for low, high, run in _merged(marked):
            text = readable(_split_fields(whole[low:high])[0])
            if not text.strip():
                continue
            if run.hidden:
                hidden.append(_Marked(label, text, run))
            if run.deleted or run.inserted:
                revisions.append(_Marked(label, text, run))

        visible, found = _split_fields("".join(shown))
        fields.extend(found)
        text = readable(visible)
        if text.strip():
            stories.append(Story(name=label, text=text))

    comments, notes = read_comments(word, table, annotations)
    remarks.extend(notes)

    if at > len(whole):
        remarks.append(
            f"this file says it holds {at} characters and the piece table gives "
            f"{len(whole)}, so the last story is short of what was claimed"
        )

    return WordText(
        stories=tuple(stories),
        comments=comments,
        revisions=tuple(
            Revision(
                kind="deletion" if mark.run.deleted else "insertion",
                text=mark.text,
                author=mark.run.author,
                date=mark.run.date,
                part=mark.part,
            )
            for mark in revisions
        ),
        hidden=tuple(Story(name=mark.part, text=mark.text) for mark in hidden),
        fields=tuple(fields),
        properties_unread=unread,
        remarks=tuple(remarks),
    )


__all__ = [
    "FieldCode",
    "NotAWordDocument",
    "Piece",
    "Story",
    "WordText",
    "read_word",
]
