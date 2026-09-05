"""Turning a file into text, and saying how much text there was to turn.

Dispatch is by content, not by extension. A `.txt` holding a PDF is a PDF, and
a forensic tool that trusts a filename has already been fooled once.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from .docx import read_docx
from .image import read_image
from .model import Extraction, TextUnit, UnreadableFile
from .odf import read_odf
from .pdf import read_pdf
from .plain import read_plain
from .presentation import read_odp, read_pptx
from .spreadsheet import odf_flavour, read_ods, read_xlsx

__all__ = ["Extraction", "TextUnit", "UnreadableFile", "read"]

def _digest(path: Path) -> str:
    """sha256 of the file, read in blocks so a large one costs no memory.

    Failure is empty rather than fatal: the digest annotates a report, and a
    file that could be read for its contents and not for its bytes is a case
    worth reporting anyway.
    """
    try:
        block = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                block.update(chunk)
        return block.hexdigest()
    except OSError:
        return ""


def read(path: str | Path) -> Extraction:
    """Read `path` into text units, or raise `UnreadableFile`."""
    path = Path(path)
    try:
        head = path.open("rb").read(8)
    except OSError as exc:
        raise UnreadableFile(f"cannot open {path}: {exc}") from exc

    # Attached once here rather than in each reader, so a format added later
    # cannot arrive without it.
    return dataclasses.replace(_dispatch(path, head), sha256=_digest(path))


def _dispatch(path: Path, head: bytes) -> Extraction:
    if head.startswith(b"%PDF-"):
        return read_pdf(path)
    if head.startswith(b"\xff\xd8\xff"):
        return read_image(path)
    if head.startswith(b"PK\x03\x04"):
        # Every OOXML and ODF file is a zip. Which one it is depends on what is
        # inside, so the contents decide - not the extension, which a forensic
        # tool has no business trusting.
        return _read_zip(path)
    return read_plain(path)


def _read_zip(path: Path) -> Extraction:
    """An OOXML document, an OpenDocument one, or neither."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc

    if "word/document.xml" in names:
        return read_docx(path)
    if "xl/workbook.xml" in names:
        return read_xlsx(path)
    if "ppt/presentation.xml" in names:
        return read_pptx(path)
    if "content.xml" in names:
        # Every OpenDocument file is a `content.xml`, and until the flavour is
        # asked for they all look like text documents. Sending a spreadsheet to
        # the text reader is not a near miss: it reads the hidden rows and
        # columns as visible prose and then reports the workbook clean.
        with zipfile.ZipFile(path) as archive:
            flavour = odf_flavour(archive)
        if flavour == "spreadsheet":
            return read_ods(path)
        if flavour == "presentation":
            return read_odp(path)
        return read_odf(path)
    raise UnreadableFile(
        f"{path.name} is a zip but not a document unmasker reads: it holds "
        "no Word document, workbook or OpenDocument body"
    )
