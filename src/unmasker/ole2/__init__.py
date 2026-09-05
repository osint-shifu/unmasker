"""The compound file: a filesystem inside a file.

`.doc`, `.xls` and `.ppt` are each a FAT filesystem in a single file - sectors,
an allocation table, a directory tree - with a second, smaller filesystem
nested inside for streams below a cutoff, normally 4096 bytes. Nothing in the
standard library reads one, and this project has one runtime dependency which
is not becoming two, so it is written here.

**The mini stream is not optional.** In a real Word 97 document every stream
worth having - the metadata, the text, the table - is under the cutoff and
therefore lives in the mini stream rather than in sectors. A reader that
handled full sectors first and left the small ones for later would return
nothing at all from a genuine file while passing any suite built from the
specification. The specimen was read before this module was written for exactly
that reason.

What is here is the container. What a `WordDocument` stream means is a
different format and a different problem; this hands over the bytes.

Everything is bounds-checked and every chain is cycle-checked, because this
reads files somebody else wrote and some of them are wrong on purpose.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")

#: Sector numbers at or above this are not sectors. `0xFFFFFFFC` and up are
#: DIFSECT, FATSECT, ENDOFCHAIN and FREESECT; read as signed they are negative,
#: which is what the chain walkers test for.
MAXREGSECT = 0xFFFFFFFA

EMPTY, STORAGE, STREAM, ROOT = 0, 1, 2, 5

#: A directory entry is this many bytes, always, in both versions.
ENTRY = 128

#: How many links a chain may follow before this gives up. A file large enough
#: to need more than this is larger than anything this tool is meant for, and
#: the cap is what stops a corrupt allocation table spinning.
MAX_LINKS = 1 << 20


class NotACompoundFile(ValueError):
    """The bytes are not a compound file, or are damaged past reading."""


@dataclass(frozen=True)
class Entry:
    """One directory entry: a stream, a storage, or the root."""

    name: str
    kind: int
    start: int
    size: int
    child: int
    left: int
    right: int


class CompoundFile:
    """Read-only access to the streams in a compound file."""

    def __init__(self, data: bytes) -> None:
        if not data.startswith(SIGNATURE):
            raise NotACompoundFile("this does not begin like a compound file")
        if len(data) < 512:
            raise NotACompoundFile("a compound file cannot be shorter than its header")

        self._data = data
        order, sector_shift, mini_shift = struct.unpack("<HHH", data[28:34])
        if order != 0xFFFE:
            raise NotACompoundFile(f"unsupported byte order {order:#06x}")
        if not 7 <= sector_shift <= 16 or not 2 <= mini_shift < sector_shift:
            raise NotACompoundFile("the sector sizes in the header are not usable")

        self.sector_size = 1 << sector_shift
        self.mini_size = 1 << mini_shift

        (
            _dir_count,
            fat_count,
            first_dir,
            _transaction,
            self.cutoff,
            first_minifat,
            minifat_count,
            first_difat,
            difat_count,
        ) = struct.unpack("<IIIIIIIII", data[40:76])

        self._fat = self._read_fat(fat_count, first_difat, difat_count)
        self._entries = self._read_directory(first_dir)
        self._minifat = self._read_minifat(first_minifat, minifat_count)
        self._mini_stream = self._read_mini_stream()
        self._streams = self._walk()

    # -- sectors ---------------------------------------------------------

    def _sector(self, number: int) -> bytes:
        """One sector's bytes. The header occupies the space of the first."""
        if number < 0 or number > MAXREGSECT:
            raise NotACompoundFile(f"sector {number} is not a sector")
        at = self.sector_size + number * self.sector_size
        block = self._data[at : at + self.sector_size]
        if len(block) < self.sector_size:
            # A truncated file. Padding keeps the arithmetic honest and lets
            # the directory still be read; what is missing shows up as a short
            # stream rather than as an exception from deep inside a chain.
            block = block.ljust(self.sector_size, b"\x00")
        return block

    def _chain(self, start: int, table: list[int]) -> list[int]:
        """Follow an allocation chain, refusing to go round twice."""
        out: list[int] = []
        seen: set[int] = set()
        at = start
        while 0 <= at <= MAXREGSECT and at < len(table) and at not in seen:
            seen.add(at)
            out.append(at)
            at = table[at]
            if len(out) > MAX_LINKS:
                raise NotACompoundFile("an allocation chain does not end")
        return out

    # -- tables ----------------------------------------------------------

    def _read_fat(self, fat_count: int, first_difat: int, difat_count: int) -> list[int]:
        per_sector = self.sector_size // 4
        places = list(struct.unpack("<109i", self._data[76:512]))

        # The DIFAT continues in its own sectors when 109 entries are not
        # enough. Each holds `per_sector - 1` FAT locations and points at the
        # next one with its final word.
        at, guard = first_difat, 0
        while 0 <= at <= MAXREGSECT and guard <= difat_count + 1:
            block = self._sector(at)
            values = struct.unpack(f"<{per_sector}i", block)
            places.extend(values[:-1])
            at = values[-1]
            guard += 1

        fat: list[int] = []
        for place in places[: fat_count or len(places)]:
            if not 0 <= place <= MAXREGSECT:
                continue
            fat.extend(struct.unpack(f"<{per_sector}i", self._sector(place)))
        return fat

    def _read_minifat(self, first: int, count: int) -> list[int]:
        per_sector = self.sector_size // 4
        table: list[int] = []
        for number in self._chain(first, self._fat)[: count or None]:
            table.extend(struct.unpack(f"<{per_sector}i", self._sector(number)))
        return table

    def _read_directory(self, first: int) -> list[Entry]:
        blob = b"".join(self._sector(n) for n in self._chain(first, self._fat))
        entries = []
        for at in range(0, len(blob) - ENTRY + 1, ENTRY):
            raw = blob[at : at + ENTRY]
            length = struct.unpack("<H", raw[64:66])[0]
            # The length counts the terminating NUL, in bytes, and a wrong one
            # is the commonest damage in the wild.
            name = raw[: max(0, min(length, 64) - 2)].decode("utf-16-le", "replace")
            left, right, child = struct.unpack("<iii", raw[68:80])
            start, size = struct.unpack("<IQ", raw[116:128])
            entries.append(
                Entry(
                    name=name,
                    kind=raw[66],
                    start=start,
                    size=size,
                    child=child,
                    left=left,
                    right=right,
                )
            )
        return entries

    def _read_mini_stream(self) -> bytes:
        """The root entry's own stream, which the small streams live inside."""
        if not self._entries or self._entries[0].kind != ROOT:
            return b""
        root = self._entries[0]
        blob = b"".join(self._sector(n) for n in self._chain(root.start, self._fat))
        return blob[: root.size]

    # -- directory tree --------------------------------------------------

    def _walk(self) -> dict[str, Entry]:
        """Every stream, by path.

        The directory is a red-black tree per storage. Names are joined with
        `/` so a stream inside an embedded object cannot be confused with one
        beside it, which matters because a `.doc` can carry another document.
        """
        found: dict[str, Entry] = {}
        if not self._entries:
            return found

        seen: set[int] = set()
        stack: list[tuple[int, str]] = [(self._entries[0].child, "")]
        while stack:
            index, prefix = stack.pop()
            if not 0 <= index < len(self._entries) or index in seen:
                continue
            seen.add(index)
            entry = self._entries[index]
            path = f"{prefix}{entry.name}"

            if entry.kind == STREAM:
                found[path] = entry
            elif entry.kind == STORAGE:
                stack.append((entry.child, f"{path}/"))

            stack.append((entry.left, prefix))
            stack.append((entry.right, prefix))
        return found

    # -- the interface ---------------------------------------------------

    @property
    def names(self) -> tuple[str, ...]:
        """Every stream in the file, by path. The root is not one."""
        return tuple(self._streams)

    def read(self, name: str) -> bytes:
        """One stream's bytes, at the length the directory claims."""
        entry = self._streams[name]
        if entry.size < self.cutoff:
            # Small streams are not in sectors at all: they are packed into
            # the root entry's stream, allocated in mini sectors. This is the
            # half a specification-first reader is entitled to postpone, and
            # in a real Word file it is the half that holds everything.
            blob = b"".join(
                self._mini_stream[n * self.mini_size : (n + 1) * self.mini_size]
                for n in self._chain(entry.start, self._minifat)
            )
        else:
            blob = b"".join(self._sector(n) for n in self._chain(entry.start, self._fat))
        return blob[: entry.size]


__all__ = ["CompoundFile", "Entry", "NotACompoundFile"]
