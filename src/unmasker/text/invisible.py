"""Tier 2: characters that change what a reader sees without changing what a
parser gets.

Pure string analysis, so it runs on anything that yields text - PDF, DOCX, HTML,
Markdown, source code - and needs none of the PDF geometry. It also covers the
prompt-injection case on its own: a retrieval pipeline reads the tag characters
below, and the human reviewing the document never sees them.

## The hard part is the silence

Finding a zero-width joiner is trivial. Knowing when *not* to report one is the
whole job:

- U+200D inside `\U0001f468‍\U0001f469‍\U0001f467` is a family emoji.
- U+200C between Persian letters is ordinary orthography, not a payload.
- A byte-order mark at offset 0 is how the file was saved.
- Japanese mixes Han, Hiragana and Katakana in one word as a matter of course.

Each of those is suppressed here, and each has a test. A detector that fires on
them teaches its reader to skip the report, and a report that gets skipped is
worth less than no report - which is the same lesson `filetrail` learned about
ranking claims, arriving from a different direction.

## What it deliberately does not do

It does not decide that anything is an attack. A word spanning two scripts is
reported as spanning two scripts, with `Basis.CIRCUMSTANTIAL`, and the reader
decides. `CLAUDE.md`: never state something the evidence does not support.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator

from ..findings import Basis, Finding, Location

# The marker that makes an invisible character visible in the `machine reads`
# column. Mathematical angle brackets, because ASCII `<>` is ordinary content in
# every HTML and XML document this tool will ever be pointed at.
OPEN, CLOSE = "⟨", "⟩"

# --------------------------------------------------------------------------
# character classes
# --------------------------------------------------------------------------

ZERO_WIDTH: frozenset[int] = frozenset(
    {
        0x00AD,  # SOFT HYPHEN
        0x180E,  # MONGOLIAN VOWEL SEPARATOR
        0x200B,  # ZERO WIDTH SPACE
        0x200C,  # ZERO WIDTH NON-JOINER
        0x200D,  # ZERO WIDTH JOINER
        0x2060,  # WORD JOINER
        0x2061,  # FUNCTION APPLICATION
        0x2062,  # INVISIBLE TIMES
        0x2063,  # INVISIBLE SEPARATOR
        0x2064,  # INVISIBLE PLUS
        0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / byte-order mark
        0x115F,  # HANGUL CHOSEONG FILLER
        0x1160,  # HANGUL JUNGSEONG FILLER
        0x3164,  # HANGUL FILLER
        0xFFA0,  # HALFWIDTH HANGUL FILLER
    }
)

# Direction controls. Overrides are the ones that reorder text on screen; the
# marks and isolates are weaker but belong to the same conversation.
BIDI_OPEN: frozenset[int] = frozenset({0x202A, 0x202B, 0x202D, 0x202E})
BIDI_POP = 0x202C
BIDI_ISOLATE: frozenset[int] = frozenset({0x2066, 0x2067, 0x2068})
BIDI_POP_ISOLATE = 0x2069
BIDI_MARK: frozenset[int] = frozenset({0x200E, 0x200F})
BIDI: frozenset[int] = BIDI_OPEN | BIDI_ISOLATE | BIDI_MARK | {BIDI_POP, BIDI_POP_ISOLATE}

# Deprecated language tags, and the channel of choice for hiding instructions in
# text meant for a language model. They decode straight to ASCII, so unlike a
# zero-width run they carry a readable message.
TAG_START, TAG_END = 0xE0000, 0xE007F

# Scripts that use U+200C and U+200D as ordinary orthography rather than as
# something hidden.
_JOINING: tuple[tuple[int, int], ...] = (
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x074F),  # Syriac
    (0x0750, 0x077F),  # Arabic Supplement
    (0x0780, 0x07BF),  # Thaana
    (0x07C0, 0x07FF),  # NKo
    (0x0840, 0x085F),  # Mandaic
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0x0900, 0x097F),  # Devanagari
    (0x0980, 0x09FF),  # Bengali
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Oriya
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
    (0x1000, 0x109F),  # Myanmar
    (0x1780, 0x17FF),  # Khmer
    (0x1800, 0x18AF),  # Mongolian
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFE),  # Arabic Presentation Forms-B, stopping short of U+FEFF
)

# Approximate Extended_Pictographic. `unicodedata` does not expose the property,
# and pulling a table in for it would cost a second dependency, which
# `HANDOFF.md` requires be argued for in writing. These ranges cover the emoji a
# document realistically contains; a joiner between two of them is a sequence.
_PICTOGRAPHIC: tuple[tuple[int, int], ...] = (
    (0x00A9, 0x00A9),
    (0x00AE, 0x00AE),
    (0x203C, 0x203C),
    (0x2049, 0x2049),
    (0x2122, 0x2122),
    (0x2139, 0x2139),
    (0x2194, 0x21AA),
    (0x231A, 0x231B),
    (0x2328, 0x2328),
    (0x23CF, 0x23FA),
    (0x24C2, 0x24C2),
    (0x25AA, 0x25FE),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x3030, 0x3030),
    (0x303D, 0x303D),
    (0x3297, 0x3299),
    (0xFE0E, 0xFE0F),  # variation selectors 15 and 16, worn by emoji
    (0x1F000, 0x1FAFF),
    (0xE0020, 0xE007F),  # tag sequences inside flag emoji
)

# Scripts, coarse but enough to answer "does this one word span two of them".
# Only the scripts that actually generate confusables with Latin need to be
# separated precisely; the rest are here so that ordinary text in them is
# recognised as single-script and stays quiet.
_SCRIPTS: tuple[tuple[int, int, str], ...] = (
    (0x0041, 0x005A, "Latin"),
    (0x0061, 0x007A, "Latin"),
    (0x00C0, 0x024F, "Latin"),
    (0x1E00, 0x1EFF, "Latin"),
    (0x2C60, 0x2C7F, "Latin"),
    (0xA720, 0xA7FF, "Latin"),
    (0x0370, 0x03FF, "Greek"),
    (0x1F00, 0x1FFF, "Greek"),
    (0x0400, 0x052F, "Cyrillic"),
    (0x2DE0, 0x2DFF, "Cyrillic"),
    (0xA640, 0xA69F, "Cyrillic"),
    (0x0530, 0x058F, "Armenian"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0750, 0x077F, "Arabic"),
    (0x08A0, 0x08FF, "Arabic"),
    (0x0700, 0x074F, "Syriac"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0E00, 0x0E7F, "Thai"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x13A0, 0x13FF, "Cherokee"),
    (0x1100, 0x11FF, "Hangul"),
    (0x3130, 0x318F, "Hangul"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x3400, 0x4DBF, "Han"),
    (0x4E00, 0x9FFF, "Han"),
    (0xF900, 0xFAFF, "Han"),
)

# Combinations that are ordinary writing rather than a mixed-script word.
# Japanese runs Han, Hiragana and Katakana together inside a single word, and
# Latin turns up in all of them. None of these pairs produces the confusables
# that make the detector worth having.
_EXPECTED_MIX = frozenset({"Han", "Hiragana", "Katakana", "Hangul", "Latin"})


def _in(ranges: tuple[tuple[int, int], ...], cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _script(ch: str) -> str | None:
    """The script of a letter, or None for anything that is not one.

    Category is checked first so that `×` and `÷`, which sit inside
    the Latin-1 range, are not mistaken for Latin letters.
    """
    if not unicodedata.category(ch).startswith("L"):
        return None
    cp = ord(ch)
    for lo, hi, name in _SCRIPTS:
        if lo <= cp <= hi:
            return name
    return None


def _name(ch: str) -> str:
    return unicodedata.name(ch, f"U+{ord(ch):04X}")


def _label(ch: str) -> str:
    return f"U+{ord(ch):04X}"


# --------------------------------------------------------------------------
# positions
# --------------------------------------------------------------------------


class _Lines:
    """Maps absolute offsets to line and column, and back to the line text.

    Columns are 1-based and counted in characters, which is what a reader
    counting along a printed line will get.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.starts: list[int] = []
        self.bodies: list[str] = []
        offset = 0
        for raw in text.splitlines(keepends=True):
            self.starts.append(offset)
            self.bodies.append(raw.rstrip("\r\n"))
            offset += len(raw)
        if not self.starts:
            self.starts, self.bodies = [0], [""]

    def index(self, offset: int) -> int:
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def locate(self, offset: int) -> Location:
        i = self.index(offset)
        return Location(line=i + 1, column=offset - self.starts[i] + 1)


def _runs(indices: list[int]) -> Iterator[list[int]]:
    """Group sorted offsets into maximal runs of consecutive ones.

    A run at one site is one place for a reader to look, not several.
    """
    run: list[int] = []
    for i in indices:
        if run and i == run[-1] + 1:
            run.append(i)
        else:
            if run:
                yield run
            run = [i]
    if run:
        yield run


def _mark(body: str, hidden: set[int], annotate=None) -> str:
    """The line as a parser gets it, with the invisible parts made explicit."""
    out = []
    for i, ch in enumerate(body):
        if i in hidden:
            extra = annotate(ch) if annotate else ""
            out.append(f"{OPEN}{_label(ch)}{extra}{CLOSE}")
        else:
            out.append(ch)
    return "".join(out)


def _strip(body: str, hidden: set[int]) -> str:
    return "".join(ch for i, ch in enumerate(body) if i not in hidden)


# --------------------------------------------------------------------------
# zero-width
# --------------------------------------------------------------------------


def _benign_zero_width(text: str) -> set[int]:
    """Offsets holding a zero-width character that is doing an honest job."""
    benign: set[int] = set()
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp not in ZERO_WIDTH:
            continue
        if cp == 0xFEFF and i == 0:
            benign.add(i)  # byte-order mark: how the file was saved
            continue
        if cp not in (0x200C, 0x200D):
            continue
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if not prev or not nxt:
            continue
        pair = (ord(prev), ord(nxt))
        if cp == 0x200D and all(_in(_PICTOGRAPHIC, c) for c in pair):
            benign.add(i)  # emoji sequence
        elif all(_in(_JOINING, c) for c in pair):
            benign.add(i)  # ordinary orthography in a joining script
    return benign


def _zero_width(text: str, lines: _Lines) -> list[Finding]:
    benign = _benign_zero_width(text)
    hits = [i for i, ch in enumerate(text) if ord(ch) in ZERO_WIDTH and i not in benign]
    if not hits:
        return []

    per_line: dict[int, set[int]] = {}
    for i in hits:
        li = lines.index(i)
        per_line.setdefault(li, set()).add(i - lines.starts[li])

    found = []
    for run in _runs(hits):
        li = lines.index(run[0])
        body = lines.bodies[li]
        rel = per_line[li]
        chars = [text[i] for i in run]
        names = sorted({_name(c) for c in chars})
        if len(chars) == 1:
            summary = f"{names[0]} ({_label(chars[0])}), invisible to a reader"
        else:
            summary = f"{len(chars)} invisible characters: {', '.join(names)}"
        found.append(
            Finding(
                detector="zero-width",
                basis=Basis.DIRECT,
                summary=summary,
                human_sees=_strip(body, rel),
                machine_reads=_mark(body, rel),
                location=lines.locate(run[0]),
                codepoints=tuple(_label(c) for c in chars),
            )
        )
    return found


# --------------------------------------------------------------------------
# bidi controls
# --------------------------------------------------------------------------


def _unterminated(text: str) -> set[int]:
    """Offsets of overrides and isolates never closed before the end."""
    embed: list[int] = []
    isolate: list[int] = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp in BIDI_OPEN:
            embed.append(i)
        elif cp == BIDI_POP and embed:
            embed.pop()
        elif cp in BIDI_ISOLATE:
            isolate.append(i)
        elif cp == BIDI_POP_ISOLATE and isolate:
            isolate.pop()
    return set(embed) | set(isolate)


def _apply_overrides(body: str) -> str:
    """What the line renders as, once a right-to-left override has had its way.

    This is not the Unicode Bidirectional Algorithm. It resolves the one case
    the detector is about - an explicit override reversing a run of otherwise
    left-to-right text, which is how `invoice‮gpj.exe` reads as a JPEG -
    and it leaves embeddings and isolates alone rather than guessing. The
    report says `a reader sees`, not `this is what it is`, for that reason.
    """
    out: list[str] = []
    i = 0
    while i < len(body):
        cp = ord(body[i])
        if cp == 0x202E:  # RIGHT-TO-LEFT OVERRIDE
            j = i + 1
            segment: list[str] = []
            while j < len(body) and ord(body[j]) not in (BIDI_POP, BIDI_POP_ISOLATE):
                if ord(body[j]) not in BIDI:
                    segment.append(body[j])
                j += 1
            out.append("".join(reversed(segment)))
            i = j + 1
        elif cp in BIDI:
            i += 1  # a control of its own has no glyph
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def _bidi(text: str, lines: _Lines) -> list[Finding]:
    hits = [i for i, ch in enumerate(text) if ord(ch) in BIDI]
    if not hits:
        return []
    open_ended = _unterminated(text)

    per_line: dict[int, set[int]] = {}
    for i in hits:
        li = lines.index(i)
        per_line.setdefault(li, set()).add(i - lines.starts[li])

    found = []
    for run in _runs(hits):
        li = lines.index(run[0])
        body = lines.bodies[li]
        rel = per_line[li]
        chars = [text[i] for i in run]
        names = ", ".join(_name(c) for c in chars)
        summary = f"{names} ({', '.join(_label(c) for c in chars)})"
        if any(i in open_ended for i in run):
            summary += ", not closed before the end of the text"
        found.append(
            Finding(
                detector="bidi-control",
                basis=Basis.DIRECT,
                summary=summary,
                human_sees=_apply_overrides(body),
                machine_reads=_mark(body, rel),
                location=lines.locate(run[0]),
                codepoints=tuple(_label(c) for c in chars),
            )
        )
    return found


# --------------------------------------------------------------------------
# tag characters
# --------------------------------------------------------------------------


def _tags(text: str, lines: _Lines) -> list[Finding]:
    hits = [i for i, ch in enumerate(text) if TAG_START <= ord(ch) <= TAG_END]
    if not hits:
        return []

    per_line: dict[int, set[int]] = {}
    for i in hits:
        li = lines.index(i)
        per_line.setdefault(li, set()).add(i - lines.starts[li])

    found = []
    for run in _runs(hits):
        li = lines.index(run[0])
        body = lines.bodies[li]
        rel = per_line[li]
        chars = [text[i] for i in run]
        # U+E0020..U+E007E mirror printable ASCII. U+E0001 and U+E007F are the
        # begin and cancel markers and spell nothing.
        decoded = "".join(chr(ord(c) - TAG_START) for c in chars if 0xE0020 <= ord(c) <= 0xE007E)
        # The message itself belongs in `machine reads`, where it sits in
        # context, and in `decodes to`, where it sits clean. Repeating it in
        # the summary as well is the third copy on one screen.
        summary = f"{len(chars)} tag characters, invisible in every renderer"
        if not decoded:
            summary += ", spelling nothing printable"
        reading = _strip(body, rel)
        if decoded:
            # Show the message, not a row of codepoints. What was smuggled is
            # the finding; that it arrived as U+E0053 and friends is detail the
            # `codepoints` field already carries in full.
            marked = (
                body[: min(rel)] + f"{OPEN}tag characters: {decoded}{CLOSE}" + body[max(rel) + 1 :]
            )
        else:
            marked = _mark(body, rel)
        found.append(
            Finding(
                detector="tag-characters",
                basis=Basis.DIRECT,
                summary=summary,
                human_sees=reading,
                machine_reads=marked,
                location=lines.locate(run[0]),
                codepoints=tuple(_label(c) for c in chars),
                decoded=decoded or None,
            )
        )
    return found


# --------------------------------------------------------------------------
# mixed script
# --------------------------------------------------------------------------


def _mixed_script(text: str, lines: _Lines) -> list[Finding]:
    found = []
    for li, body in enumerate(lines.bodies):
        pos = 0
        for token in body.split(" "):
            if not token:
                pos += 1
                continue
            scripts = {s for s in (_script(c) for c in token) if s}
            if len(scripts) > 1 and not scripts <= _EXPECTED_MIX:
                # The minority scripts are the ones worth pointing at.
                counts = {s: 0 for s in scripts}
                for ch in token:
                    s = _script(ch)
                    if s:
                        counts[s] += 1
                majority = max(counts, key=lambda s: counts[s])
                odd = {
                    pos + k for k, ch in enumerate(token) if _script(ch) and _script(ch) != majority
                }
                found.append(
                    Finding(
                        detector="mixed-script",
                        basis=Basis.CIRCUMSTANTIAL,
                        summary=(
                            f'"{token}" mixes ' + " and ".join(sorted(scripts)) + " in one word"
                        ),
                        human_sees=body,
                        machine_reads=_mark(body, odd, annotate=lambda ch: f" {_script(ch)}"),
                        # The word is named in the summary; the location points
                        # at the character that differs, which is what a reader
                        # opening the file is trying to find.
                        location=Location(line=li + 1, column=min(odd) + 1),
                        codepoints=tuple(
                            _label(ch) for ch in token if _script(ch) != majority and _script(ch)
                        ),
                    )
                )
            pos += len(token) + 1
    return found


# --------------------------------------------------------------------------


def scan_text(text: str) -> list[Finding]:
    """Every tier-2 finding in `text`, in document order.

    Order is position, never strength. Nothing here ranks a bidi override
    against a homoglyph: they are different questions, and `filetrail` proved
    what happens when different questions are made to compete.
    """
    if not text:
        return []
    lines = _Lines(text)
    found = (
        _zero_width(text, lines)
        + _bidi(text, lines)
        + _tags(text, lines)
        + _mixed_script(text, lines)
    )
    return sorted(found, key=lambda f: f.location.sort_key)
