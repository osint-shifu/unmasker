"""Turning a file into text, and saying how much text there was to turn.

Dispatch is by content, not by extension. A `.txt` holding a PDF is a PDF, and
a forensic tool that trusts a filename has already been fooled once.
"""

from __future__ import annotations

from pathlib import Path

from .docx import read_docx
from .model import Extraction, TextUnit, UnreadableFile
from .odf import read_odf
from .pdf import read_pdf
from .plain import read_plain
from .spreadsheet import odf_flavour, read_ods, read_xlsx

__all__ = ["Extraction", "TextUnit", "UnreadableFile", "read"]

NO_SLIDES = (
    "is a presentation, and unmasker does not read slides yet. It refuses "
    "rather than read the deck as a text document, which would report a "
    "hidden slide and a speaker note as visible text and then call the file "
    "clean"
)
"""Why a deck is refused instead of half-read.

Reading it as prose is not a near miss. It is the failure the spreadsheet
reader was written to remove - a concealed layer handed to the detectors as
though a person could see it, followed by an all-clear - and it would arrive
here one container over. Refusing says less and says nothing untrue.

The reader that would replace this is blocked on a specimen, not on the code:
`libreoffice-impress` is not installed on this machine, and `CONTRIBUTING.md` is
explicit that a detector proved only against a hand-built fixture is the shape
of the bug that started this project.
"""


def read(path: str | Path) -> Extraction:
    """Read `path` into text units, or raise `UnreadableFile`."""
    path = Path(path)
    try:
        head = path.open("rb").read(8)
    except OSError as exc:
        raise UnreadableFile(f"cannot open {path}: {exc}") from exc

    if head.startswith(b"%PDF-"):
        return read_pdf(path)
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
        raise UnreadableFile(f"{path.name} {NO_SLIDES}")
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
            raise UnreadableFile(f"{path.name} {NO_SLIDES}")
        return read_odf(path)
    raise UnreadableFile(
        f"{path.name} is a zip but not a document unmasker reads: it holds "
        "no Word document, workbook or OpenDocument body"
    )
