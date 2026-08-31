"""PDF text, page by page.

`pypdf` owns the object model, decompression, font decoding and text
extraction; that division is argued for in `HANDOFF.md` and is most of the
reason it is a dependency at all. What this module adds is the part `pypdf`
cannot answer: whether a page that produced no text had none to produce.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from .model import Extraction, TextUnit, UnreadableFile


def _has_fonts(page) -> bool:
    """Whether the page's resources declare any font at all.

    A page with no fonts cannot carry a text object, so "no text found" there
    means *nothing to search*. A page with fonts that still yields nothing is a
    different statement, and the report is required to keep them apart.
    """
    try:
        resources = page.get("/Resources")
        if resources is None:
            return False
        fonts = resources.get_object().get("/Font")
        return bool(fonts is not None and fonts.get_object())
    except Exception:
        # An unreadable resource dictionary is not evidence either way, and
        # claiming "no text layer" on the strength of it would be a verdict the
        # file does not support.
        return True


def read_pdf(path: Path) -> Extraction:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise UnreadableFile(f"{path.name} could not be parsed as a PDF: {exc}") from exc

    remarks: list[str] = []

    if reader.is_encrypted:
        try:
            opened = reader.decrypt("")
        except Exception:
            opened = 0
        if not opened:
            raise UnreadableFile(
                f"{path.name} is encrypted and needs a password unmasker does not have"
            )
        remarks.append(
            "the file is encrypted; it opened with an empty password, "
            "which is how most 'protected' PDFs are made"
        )

    units: list[TextUnit] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = ""
            remarks.append(f"page {number} could not be extracted: {exc}")
        units.append(TextUnit(text=text, page=number))

        if not text.strip():
            if _has_fonts(page):
                remarks.append(
                    f"page {number} declares fonts but yielded no text; "
                    "it was searched and nothing came back"
                )
            else:
                remarks.append(
                    f"page {number} has no text layer, so there was nothing to "
                    "search on it - reading what is under a mark there would "
                    "need OCR, which unmasker does not do"
                )

    if not units:
        remarks.append("the file has no pages")

    return Extraction(kind="pdf", units=tuple(units), remarks=tuple(remarks))
