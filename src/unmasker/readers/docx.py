"""DOCX body text, for the detectors that only need characters.

This reads what a reader *sees*: the `w:t` runs of the document body, its
headers and its footers. It deliberately does not read `w:delText`, the deleted
text that tracked changes leave inside the file - that is a tier-4 finding with
its own shape (who deleted what, and when), and folding it in here would report
it as ordinary body text, which is the opposite of what it is.

No new dependency: a DOCX is a zip of XML, and both are in the standard library.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .model import Extraction, TextUnit, UnreadableFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _parts(archive: zipfile.ZipFile) -> list[str]:
    """Body first, then headers and footers, in a stable order."""
    names = set(archive.namelist())
    ordered = ["word/document.xml"] if "word/document.xml" in names else []
    ordered += sorted(
        n for n in names if n.startswith(("word/header", "word/footer")) and n.endswith(".xml")
    )
    return ordered


def _text_of(xml: bytes) -> str:
    """Paragraph text, one paragraph per line.

    Tabs become tabs and `w:br` becomes a newline, so a column of values does
    not collapse into one run and report a column number a reader cannot find.
    """
    root = ElementTree.fromstring(xml)
    lines: list[str] = []
    for para in root.iter(f"{W}p"):
        buf: list[str] = []
        for node in para.iter():
            if node.tag == f"{W}t":
                buf.append(node.text or "")
            elif node.tag == f"{W}tab":
                buf.append("\t")
            elif node.tag == f"{W}br":
                buf.append("\n")
        lines.append("".join(buf))
    return "\n".join(lines)


def read_docx(path: Path) -> Extraction:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc

    with archive:
        names = archive.namelist()
        if "word/document.xml" not in names:
            hint = ""
            if "content.xml" in names:
                hint = "; it looks like an OpenDocument file, which unmasker does not read yet"
            raise UnreadableFile(f"{path.name} is a zip but not a Word document{hint}")

        units: list[TextUnit] = []
        remarks: list[str] = []
        for name in _parts(archive):
            try:
                text = _text_of(archive.read(name))
            except ElementTree.ParseError as exc:
                remarks.append(f"{name} is not well-formed XML and was skipped: {exc}")
                continue
            if text.strip():
                units.append(TextUnit(text=text))

        if any(n.startswith("word/comments") for n in names):
            remarks.append("the file carries comments, which unmasker does not read yet")
        if not units:
            remarks.append("the document body holds no text, so there was nothing to search")

    return Extraction(kind="docx", units=tuple(units), remarks=tuple(remarks))
