"""PDF text, page by page.

`pypdf` owns the object model, decompression, font decoding and text
extraction; that division is argued for in `HANDOFF.md` and is most of the
reason it is a dependency at all. What this module adds is the part `pypdf`
cannot answer: whether a page that produced no text had none to produce.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from ..pdf.interpreter import InterpretedPage, interpret_page
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
    drawn: list[InterpretedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = ""
            remarks.append(f"page {number} could not be extracted: {exc}")
        units.append(TextUnit(text=text, page=number))

        try:
            painted = interpret_page(page, number)
        except Exception as exc:
            painted = None
            remarks.append(
                f"page {number}: the content stream could not be interpreted "
                f"({exc}); nothing about what is drawn on it was established"
            )
        if painted is not None:
            drawn.append(painted)
            remarks.extend(f"page {number}: {note}" for note in painted.remarks)

        if not text.strip():
            if _has_fonts(page):
                remarks.append(
                    f"page {number} declares fonts but yielded no text; "
                    "it was searched and nothing came back"
                )
            else:
                remarks.append(
                    f"page {number} has no text layer, so there was nothing to "
                    f"search on it{_painted_summary(painted)}. Reading what is "
                    "under a mark there would need OCR, which unmasker does not do"
                )

    if not units:
        remarks.append("the file has no pages")

    return Extraction(kind="pdf", units=tuple(units), remarks=tuple(remarks), drawn=tuple(drawn))


def _painted_summary(painted: InterpretedPage | None) -> str:
    """Say what *is* on a page that has no text.

    "Nothing to search" is a dead end on its own. "Nothing to search, and one
    image is painted here" is the OCR case, named, so the reader knows what the
    next step would be rather than only that this one stopped.
    """
    if painted is None:
        return ""
    counts: dict[str, int] = {}
    for shape in painted.shapes:
        counts[shape.kind] = counts.get(shape.kind, 0) + 1
    if not counts:
        return ", and nothing is painted on it either"
    parts = [f"{n} {kind}" if n == 1 else f"{n} {kind}s" for kind, n in sorted(counts.items())]
    return (
        ", though "
        + " and ".join(parts)
        + " "
        + ("is" if sum(counts.values()) == 1 else "are")
        + " painted there"
    )
