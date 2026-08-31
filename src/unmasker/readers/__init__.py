"""Turning a file into text, and saying how much text there was to turn.

Dispatch is by content, not by extension. A `.txt` holding a PDF is a PDF, and
a forensic tool that trusts a filename has already been fooled once.
"""

from __future__ import annotations

from pathlib import Path

from .docx import read_docx
from .model import Extraction, TextUnit, UnreadableFile
from .pdf import read_pdf
from .plain import read_plain

__all__ = ["Extraction", "TextUnit", "UnreadableFile", "read"]


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
        # inside, so the zip readers decide between themselves.
        return read_docx(path)
    return read_plain(path)
