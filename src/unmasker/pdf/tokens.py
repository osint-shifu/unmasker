"""Lexing a PDF content stream.

A content stream is a postfix language: operands accumulate, an operator
consumes them. Six literal types, and a lot of ways to get the lexing wrong in
a manner that does not raise.

That last part is what this module is careful about. A tokenizer that ends a
string early, or that stops an inline image at the first `EI` in its pixel data,
does not crash - it carries on reading the middle of a picture as operators and
produces confident nonsense. For a tool whose whole claim is that it shows what
is really in the file, that is the worst failure available, so every one of
those cases has a test.

Damaged input is expected rather than exceptional. A forensic tool is pointed at
broken files on purpose, so nothing here raises on malformed bytes: an
unterminated string ends at the end of the stream, a stray delimiter is skipped,
and lexing continues.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

# PDF's own definitions. NUL counts as whitespace, which matters: it appears in
# binary image data and would otherwise look like a regular character.
WHITESPACE = frozenset(b"\x00\t\n\x0c\r ")
DELIMITERS = frozenset(b"()<>[]{}/%")


@dataclass(frozen=True)
class Name:
    """A `/Name`. Distinct from a string, because `/F1` and `(F1)` differ."""

    value: str


@dataclass(frozen=True)
class Operator:
    """A bare keyword: `re`, `f*`, `Tj`, `Do`."""

    value: str


@dataclass(frozen=True)
class InlineImage:
    """`BI … ID <bytes> EI`, lexed as a single token.

    Kept whole so the bytes can never be mistaken for operators.
    """

    params: dict
    data: bytes


_END = object()
_ARRAY_END = object()
_DICT_END = object()
_SKIP = object()  # damage stepped over; distinct from the `null` keyword

_ESCAPES = {
    ord("n"): b"\n",
    ord("r"): b"\r",
    ord("t"): b"\t",
    ord("b"): b"\b",
    ord("f"): b"\f",
    ord("("): b"(",
    ord(")"): b")",
    ord("\\"): b"\\",
}


class _Scanner:
    def __init__(self, data: bytes) -> None:
        self.d = data
        self.i = 0
        self.n = len(data)

    # -- helpers ---------------------------------------------------------

    def _skip_space(self) -> None:
        while self.i < self.n:
            c = self.d[self.i]
            if c in WHITESPACE:
                self.i += 1
            elif c == 0x25:  # '%' comment, to end of line
                while self.i < self.n and self.d[self.i] not in (0x0A, 0x0D):
                    self.i += 1
            else:
                return

    def _regular_run(self) -> bytes:
        start = self.i
        while self.i < self.n:
            c = self.d[self.i]
            if c in WHITESPACE or c in DELIMITERS:
                break
            self.i += 1
        return self.d[start : self.i]

    # -- literals --------------------------------------------------------

    def _name(self) -> Name:
        self.i += 1  # '/'
        raw = self._regular_run()
        if b"#" not in raw:
            return Name(raw.decode("latin-1"))
        out = bytearray()
        k = 0
        while k < len(raw):
            if raw[k] == 0x23 and k + 2 < len(raw):
                try:
                    out.append(int(raw[k + 1 : k + 3], 16))
                    k += 3
                    continue
                except ValueError:
                    pass
            out.append(raw[k])
            k += 1
        return Name(bytes(out).decode("latin-1"))

    def _string(self) -> bytes:
        self.i += 1  # '('
        out = bytearray()
        depth = 1
        while self.i < self.n:
            c = self.d[self.i]
            if c == 0x5C:  # backslash
                self.i += 1
                if self.i >= self.n:
                    break
                e = self.d[self.i]
                if e in _ESCAPES:
                    out += _ESCAPES[e]
                    self.i += 1
                elif 0x30 <= e <= 0x37:  # octal, up to three digits
                    digits = bytearray()
                    while self.i < self.n and len(digits) < 3 and 0x30 <= self.d[self.i] <= 0x37:
                        digits.append(self.d[self.i])
                        self.i += 1
                    out.append(int(digits, 8) & 0xFF)
                elif e in (0x0A, 0x0D):  # line continuation, emits nothing
                    self.i += 1
                    if e == 0x0D and self.i < self.n and self.d[self.i] == 0x0A:
                        self.i += 1
                else:
                    out.append(e)
                    self.i += 1
                continue
            if c == 0x28:  # '(' - legal unescaped when balanced
                depth += 1
            elif c == 0x29:  # ')'
                depth -= 1
                if depth == 0:
                    self.i += 1
                    return bytes(out)
            out.append(c)
            self.i += 1
        return bytes(out)  # unterminated: everything to the end

    def _hex_string(self) -> bytes:
        self.i += 1  # '<'
        digits = bytearray()
        while self.i < self.n and self.d[self.i] != 0x3E:
            c = self.d[self.i]
            if c not in WHITESPACE:
                digits.append(c)
            self.i += 1
        self.i += 1  # '>'
        if len(digits) % 2:
            digits.append(0x30)  # an odd trailing digit is padded with zero
        try:
            return bytes.fromhex(digits.decode("latin-1"))
        except ValueError:
            keep = bytes(c for c in digits if c in b"0123456789abcdefABCDEF")
            if len(keep) % 2:
                keep += b"0"
            return bytes.fromhex(keep.decode("latin-1"))

    def _array(self) -> list:
        self.i += 1  # '['
        items: list = []
        while True:
            tok = self._token()
            if tok is _END or tok is _ARRAY_END:
                return items
            if tok is _DICT_END:
                continue
            items.append(tok)

    def _dictionary(self) -> dict:
        self.i += 2  # '<<'
        items: list = []
        while True:
            tok = self._token()
            if tok is _END or tok is _DICT_END:
                break
            if tok is _ARRAY_END:
                continue
            items.append(tok)
        out: dict = {}
        for key, value in zip(items[0::2], items[1::2], strict=False):
            if isinstance(key, Name):
                out[key.value] = value
        if len(items) % 2 and isinstance(items[-1], Name):
            out[items[-1].value] = None  # a key with no value, kept not dropped
        return out

    # -- inline images ---------------------------------------------------

    def _inline_image(self) -> InlineImage:
        """`BI` has already been consumed. Read the parameters, then the bytes.

        The end of the data is the hard part. `EI` can occur inside the pixels,
        so it only counts when it is delimited on both sides - and when the
        dictionary gives a length, that is believed instead of guessed at.
        """
        items: list = []
        while True:
            tok = self._token()
            if tok is _END:
                break
            if isinstance(tok, Operator) and tok.value == "ID":
                break
            if tok is _ARRAY_END or tok is _DICT_END:
                continue
            items.append(tok)

        params: dict = {}
        for key, value in zip(items[0::2], items[1::2], strict=False):
            if isinstance(key, Name):
                params[key.value] = value

        # Exactly one whitespace byte separates ID from the data.
        if self.i < self.n and self.d[self.i] in WHITESPACE:
            self.i += 1

        declared = params.get("L", params.get("Length"))
        if isinstance(declared, float) and declared >= 0:
            start = self.i
            self.i = min(self.n, start + int(declared))
            data = self.d[start : self.i]
            self._skip_space()
            if self.d[self.i : self.i + 2] == b"EI":
                self.i += 2
            return InlineImage(params, data)

        start = self.i
        cursor = start
        while True:
            found = self.d.find(b"EI", cursor)
            if found < 0:
                data = self.d[start : self.n]
                self.i = self.n
                return InlineImage(params, data)
            before_ok = found > start and self.d[found - 1] in WHITESPACE
            after = self.d[found + 2 : found + 3]
            after_ok = not after or after[0] in WHITESPACE or after[0] in DELIMITERS
            if before_ok and after_ok:
                data = self.d[start:found]
                if data and data[-1] in WHITESPACE:
                    data = data[:-1]  # the delimiter itself is not image data
                self.i = found + 2
                return InlineImage(params, data)
            cursor = found + 2

    # -- dispatch --------------------------------------------------------

    def _keyword(self):
        raw = self._regular_run()
        if not raw:
            self.i += 1  # a delimiter we do not handle; do not spin on it
            return _SKIP
        text = raw.decode("latin-1")
        try:
            return float(text)
        except ValueError:
            pass
        if text == "true":
            return True
        if text == "false":
            return False
        if text == "null":
            return None
        if text == "BI":
            return self._inline_image()
        return Operator(text)

    def _token(self):
        while True:
            self._skip_space()
            if self.i >= self.n:
                return _END
            c = self.d[self.i]
            if c == 0x2F:
                return self._name()
            if c == 0x28:
                return self._string()
            if c == 0x3C:
                if self.d[self.i : self.i + 2] == b"<<":
                    return self._dictionary()
                return self._hex_string()
            if c == 0x5B:
                return self._array()
            if c == 0x5D:
                self.i += 1
                return _ARRAY_END
            if c == 0x3E:
                if self.d[self.i : self.i + 2] == b">>":
                    self.i += 2
                    return _DICT_END
                self.i += 1
                continue  # a stray '>' is damage; step over it
            if c in (0x29, 0x7B, 0x7D):
                self.i += 1
                continue  # stray ')', '{', '}'
            token = self._keyword()
            if token is _SKIP:
                continue  # `null` yields None; damage yields _SKIP
            return token

    def run(self) -> Iterator[object]:
        while True:
            self._skip_space()
            if self.i >= self.n:
                return
            start = self.i
            token = self._token()
            if token is _END:
                return
            if token is _ARRAY_END or token is _DICT_END or token is _SKIP:
                continue
            if self.i == start:  # defensive: never spin on one byte
                self.i += 1
            yield token


def tokenize(data: bytes) -> Iterator[object]:
    """Yield the tokens of `data`, never raising on malformed input.

    Operands come back as Python values - `float`, `bytes`, `list`, `dict`,
    `bool`, `None`, `Name` - and operators as `Operator`.
    """
    return _Scanner(data).run()
