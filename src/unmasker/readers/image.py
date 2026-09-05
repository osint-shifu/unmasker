"""A photograph, and the smaller photograph inside it.

The first container this tool reads that has no text at all. Everything else
here answers *what does this document say that it does not show*; a picture
says nothing, so the question becomes *what does this file show that the
picture does not* - and the answer is the preview in its EXIF, which cropping
does not regenerate.

There is deliberately no text extraction. A photograph has no text layer, and
`has_text` being false is the honest answer rather than an omission: it is what
stops the report from saying this file was searched and came back clean.
"""

from __future__ import annotations

from pathlib import Path

from ..jpeg import read as read_jpeg
from ..metadata import read_xmp
from .model import Extraction, UnreadableFile


def read_image(path: Path) -> Extraction:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise UnreadableFile(f"cannot read {path}: {exc}") from exc

    jpeg = read_jpeg(data)
    if jpeg.size is None and not jpeg.has_thumbnail:
        # Neither the picture's own dimensions nor a preview could be found,
        # which is not a photograph this reader can say anything about.
        raise UnreadableFile(
            f"{path.name} begins like a JPEG and states neither its dimensions "
            "nor a preview; it may be truncated"
        )

    remarks = list(jpeg.remarks)
    remarks.append(
        "a photograph has no text layer, so nothing here was searched for "
        "hidden characters - what is compared is the picture against the "
        "preview inside it"
    )
    if not jpeg.has_thumbnail:
        remarks.append("this file carries no preview, so there was nothing to compare")

    # XMP is not a PDF thing. An editor writes the same packet into a
    # photograph, and what it writes there is usually an edit history: what
    # this file came from, which application touched it, when. None of it is
    # on the picture.
    metadata = read_xmp(jpeg.xmp) if jpeg.xmp else None
    if metadata is not None:
        remarks.extend(metadata.remarks)

    return Extraction(
        kind="image",
        units=(),
        remarks=tuple(remarks),
        source=path,
        image=jpeg,
        metadata=metadata,
    )
