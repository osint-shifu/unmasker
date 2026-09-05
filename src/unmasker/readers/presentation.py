"""Presentations, in both families.

`unmasker` refused a deck outright until this existed, and said so rather than
half-reading it: an `.odp` is a zip with a `content.xml` in it, so it would
otherwise have reached the reader for text documents, which has no concept of a
slide nobody sees. It would have read a hidden slide and a speaker note as
ordinary visible prose and then reported the deck clean - the same defect the
spreadsheet reader was written to remove.

The refusal stood for a long time for a reason worth keeping in view: the
reader was blocked on the *specimen*, not on the parsing. Nothing on the
machine could write a deck, and a detector proved only against a hand-built
fixture is the shape of the bug that started this project.

So the rule this reader is built on is the spreadsheet's: **a slide an
application skips is not body text.** The visible slides go into the
extraction, where the character detectors will search them; the hidden ones and
every speaker note stay in the slide record and are reported as what they are.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from ..metadata import read_odf as read_odf_metadata
from ..metadata import read_ooxml
from ..metadata.detectors import describe
from ..odf.slides import read_slides as read_odf_slides
from ..ooxml.slides import read_slides as read_ooxml_slides
from ..slides import SlideRecord
from .model import Extraction, TextUnit, UnreadableFile


def _open(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc


def _assemble(record: SlideRecord, metadata) -> Extraction:
    units: list[TextUnit] = []
    remarks: list[str] = list(record.remarks)

    for slide in record.slides:
        if slide.hidden or not slide.text.strip():
            continue
        units.append(TextUnit(text=slide.text, page=slide.number))

    if metadata is not None:
        remarks.extend(metadata.remarks)
        remarks.extend(describe(metadata))

    if not record.slides:
        remarks.append("the deck holds no slides, so there was nothing to search")
    elif not units:
        # "Searched and found nothing" is not the answer here, and a reader
        # handed it would conclude the deck was empty rather than invisible.
        remarks.append(
            "no slide in this deck shows any text; everything it holds is on a "
            "slide that is skipped, or in a speaker note"
            if any(s.text.strip() or s.notes.strip() for s in record.slides)
            else "every slide in this deck is empty, so there was nothing to search"
        )

    return Extraction(
        kind="presentation",
        units=tuple(units),
        remarks=tuple(remarks),
        metadata=metadata,
        slides=record,
    )


def read_pptx(path: Path) -> Extraction:
    with _open(path) as archive:
        if "ppt/presentation.xml" not in archive.namelist():
            raise UnreadableFile(f"{path.name} is a zip but not a PresentationML deck")
        return _assemble(read_ooxml_slides(archive), read_ooxml(archive))


def read_odp(path: Path) -> Extraction:
    with _open(path) as archive:
        if "content.xml" not in archive.namelist():
            raise UnreadableFile(f"{path.name} is a zip but not an OpenDocument file")
        return _assemble(read_odf_slides(archive), read_odf_metadata(archive))
