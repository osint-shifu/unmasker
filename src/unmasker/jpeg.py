"""What a JPEG says about itself, read out of its markers.

Enough of the format to answer one question: **is the preview in this file the
same shape as the picture it claims to preview?** A photograph carries a small
copy of itself in its EXIF, and cropping the photograph does not regenerate it,
so the preview keeps showing the frame the crop removed.

## No decoder, and no second dependency

Comparing preview to picture properly means decoding two JPEGs, which means a
second runtime dependency, which `CONTRIBUTING.md` requires be argued for in
writing. It does not have to be.

A JPEG states its own dimensions in its `SOF` marker, in plain bytes, before
any pixel is decoded. The thumbnail is itself a JPEG, so it states its own the
same way. **A preview a different shape from its picture was not made from it**
- and that is header arithmetic rather than image processing.

What this deliberately cannot do is tell a stale preview from a correctly
regenerated one that happens to share the aspect ratio. `--ocr` answers that,
by reading the preview back the way it already reads a PDF page back.

## Reading a format written by whoever is being investigated

Every offset here came out of a file somebody else wrote. A length that runs
past the end, an IFD that points at itself, a marker that claims a segment
longer than the file: all of them are ordinary in a corrupt or hostile image
and none of them may raise. Everything below bounds-checks and gives up
quietly, because a forensic tool that dies on the one file that mattered has
failed at its job.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

#: Frame markers. Every `SOF` carries the dimensions; the differences between
#: them are compression choices this does not care about. `DHT`, `DAC` and the
#: restart markers are excluded because they are not frames.
SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)

#: The two IFD tags that locate a thumbnail inside the EXIF block.
THUMBNAIL_OFFSET = 0x0201
THUMBNAIL_LENGTH = 0x0202

#: Bounds on what will be believed out of a hostile file.
MAX_IFD_ENTRIES = 512
MAX_IFDS = 8


@dataclass(frozen=True)
class Size:
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass(frozen=True)
class Jpeg:
    size: Size | None = None
    thumbnail: bytes | None = None
    thumbnail_size: Size | None = None
    remarks: tuple[str, ...] = ()

    @property
    def has_thumbnail(self) -> bool:
        return self.thumbnail_size is not None


def dimensions(data: bytes) -> Size | None:
    """The picture's own dimensions, from the first frame marker.

    Walks the segment chain rather than scanning for the marker bytes: `0xFFC0`
    occurs inside compressed data constantly, and a scan finds one of those
    long before it finds the frame.
    """
    if not data.startswith(b"\xff\xd8"):
        return None

    at = 2
    end = len(data)
    while at + 4 <= end:
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            at += 2
            continue
        if marker in (0xDA, 0xD9):
            # Start of scan: the compressed data begins and there is no frame
            # header after it.
            return None
        length = struct.unpack(">H", data[at + 2 : at + 4])[0]
        if length < 2 or at + 2 + length > end:
            return None
        if marker in SOF_MARKERS and at + 9 <= end:
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return Size(width, height) if width and height else None
        at += 2 + length
    return None


def _segments(data: bytes):
    """Every marker segment, as (marker, payload). Stops at the scan."""
    at, end = 2, len(data)
    while at + 4 <= end:
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            at += 2
            continue
        if marker in (0xDA, 0xD9):
            return
        length = struct.unpack(">H", data[at + 2 : at + 4])[0]
        if length < 2 or at + 2 + length > end:
            return
        yield marker, data[at + 4 : at + 2 + length]
        at += 2 + length


def _thumbnail_from_exif(exif: bytes) -> bytes | None:
    """The bytes of the preview, out of the second IFD of the TIFF block.

    Every offset is relative to the start of the TIFF header, and every one of
    them came out of the file being examined, so each is checked against the
    block's own length before it is used.
    """
    if len(exif) < 8:
        return None

    order = exif[:2]
    if order == b"II":
        unpack = "<"
    elif order == b"MM":
        unpack = ">"
    else:
        return None

    try:
        first = struct.unpack(unpack + "I", exif[4:8])[0]
    except struct.error:
        return None

    offset, seen = first, 0
    while 0 < offset < len(exif) - 2 and seen < MAX_IFDS:
        seen += 1
        try:
            count = struct.unpack(unpack + "H", exif[offset : offset + 2])[0]
        except struct.error:
            return None
        if count > MAX_IFD_ENTRIES:
            return None

        entries = offset + 2
        tags: dict[int, int] = {}
        for index in range(count):
            at = entries + index * 12
            if at + 12 > len(exif):
                return None
            tag = struct.unpack(unpack + "H", exif[at : at + 2])[0]
            if tag in (THUMBNAIL_OFFSET, THUMBNAIL_LENGTH):
                tags[tag] = struct.unpack(unpack + "I", exif[at + 8 : at + 12])[0]

        start, length = tags.get(THUMBNAIL_OFFSET), tags.get(THUMBNAIL_LENGTH)
        if start is not None and length:
            if 0 < length < len(exif) and 0 <= start and start + length <= len(exif):
                return exif[start : start + length]
            return None

        following = entries + count * 12
        if following + 4 > len(exif):
            return None
        offset = struct.unpack(unpack + "I", exif[following : following + 4])[0]

    return None


def read(data: bytes) -> Jpeg:
    """A JPEG's own account of its size and of the preview it carries."""
    if not data.startswith(b"\xff\xd8"):
        return Jpeg(remarks=("this is not a JPEG",))

    size = dimensions(data)
    remarks: list[str] = []
    if size is None:
        remarks.append("the picture states no dimensions this reader could find")

    thumbnail = None
    for marker, payload in _segments(data):
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            thumbnail = _thumbnail_from_exif(payload[6:])
            break

    thumbnail_size = dimensions(thumbnail) if thumbnail else None
    if thumbnail and thumbnail_size is None:
        # It is there and it cannot be read, which is not the same as absent.
        remarks.append(
            "this file carries a preview whose own dimensions could not be "
            "read, so it was not compared with the picture"
        )

    return Jpeg(
        size=size,
        thumbnail=thumbnail,
        thumbnail_size=thumbnail_size,
        remarks=tuple(remarks),
    )
