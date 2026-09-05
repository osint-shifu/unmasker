"""A presentation's slides, read out of PresentationML.

Hiding is on the slide itself here, which makes it the easier of the two
families - and hides the trap that made it worth measuring:

    <p:sld ... show="0">     the slide is skipped
    <p:sld ...>              the slide is shown

**The attribute is absent when the slide is shown.** That is the opposite of
what the same producer does for a hidden *row* in a spreadsheet, where it
writes `hidden="false"` out loud on every row. A reader carrying that habit
across - testing what the attribute says rather than whether it is there -
finds no hidden slides at all, because there is nothing to read.

Order comes from `ppt/presentation.xml`, not from the part names: `slide10.xml`
sorts before `slide2.xml`, and a deck reported with its slides renumbered sends
a reader to the wrong one.

Notes live in their own parts, reached through each slide's relationships. A
notes slide repeats the slide's own text inside a placeholder, so the body
placeholder is the only one worth reading - taking every `a:t` in the part
would quote the slide back as though the speaker had written it.

No new dependency: a .pptx is a zip of XML and both are in the standard
library.
"""

from __future__ import annotations

import posixpath
import zipfile
from xml.etree import ElementTree

from ..slides import Slide, SlideRecord

MAIN = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

PRESENTATION = "ppt/presentation.xml"


def _relationships(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    folder = posixpath.dirname(part)
    rels = posixpath.join(folder, "_rels", posixpath.basename(part) + ".rels")
    if rels not in archive.namelist():
        return {}
    try:
        root = ElementTree.fromstring(archive.read(rels))
    except ElementTree.ParseError:
        return {}

    out = {}
    for node in root.iter(f"{PKG_REL}Relationship"):
        target, identifier = node.get("Target") or "", node.get("Id")
        if not identifier or not target or target.startswith(("http://", "https://")):
            continue
        out[identifier] = posixpath.normpath(posixpath.join(folder, target)).lstrip("/")
    return out


def _text_of(node) -> str:
    """Every run of text under a node, paragraph by paragraph."""
    out = []
    for paragraph in node.iter(f"{DRAWING}p"):
        line = "".join(t.text or "" for t in paragraph.iter(f"{DRAWING}t")).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def _notes_text(xml: bytes) -> str:
    """The speaker's own words, without the slide repeated back at them.

    A notes slide carries a placeholder holding a copy of the slide's text.
    Reading every `a:t` in the part quotes the slide as though the speaker had
    written it, so only the body placeholder is taken.
    """
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ""

    spoken = []
    for shape in root.iter(f"{MAIN}sp"):
        placeholder = next(shape.iter(f"{MAIN}ph"), None)
        if placeholder is not None and placeholder.get("type") == "sldImg":
            continue
        if placeholder is not None and placeholder.get("type") not in (None, "body"):
            continue
        text = _text_of(shape)
        if text:
            spoken.append(text)
    return "\n".join(spoken)


def read_slides(archive: zipfile.ZipFile) -> SlideRecord:
    names = set(archive.namelist())
    if PRESENTATION not in names:
        return SlideRecord(remarks=("the file has no ppt/presentation.xml and was not read",))

    try:
        root = ElementTree.fromstring(archive.read(PRESENTATION))
    except ElementTree.ParseError as exc:
        return SlideRecord(remarks=(f"ppt/presentation.xml is not well-formed XML: {exc}",))

    targets = _relationships(archive, PRESENTATION)

    slides: list[Slide] = []
    remarks: list[str] = []
    # Order comes from the deck rather than from the part names: `slide10.xml`
    # sorts before `slide2.xml`, and a renumbered deck sends a reader to the
    # wrong slide.
    for entry in root.iter(f"{MAIN}sldId"):
        part = targets.get(entry.get(f"{DOC_REL}id") or "")
        number = len(slides) + 1
        if part is None or part not in names:
            remarks.append(f"slide {number} is listed in the deck and its part is missing")
            slides.append(Slide(number=number))
            continue

        try:
            slide = ElementTree.fromstring(archive.read(part))
        except ElementTree.ParseError as exc:
            remarks.append(f"slide {number} is not well-formed XML and was skipped: {exc}")
            slides.append(Slide(number=number))
            continue

        # Absent means shown. The attribute is only written when it is "0".
        hidden = (slide.get("show") or "").strip() == "0"

        notes = ""
        for target in _relationships(archive, part).values():
            if "notesSlide" in target and target in names:
                notes = _notes_text(archive.read(target))
                break

        text = _text_of(slide)
        slides.append(
            Slide(
                number=number,
                text=text,
                notes=notes,
                hidden=hidden,
                title=text.splitlines()[0] if text else None,
            )
        )

    return SlideRecord(slides=tuple(slides), remarks=tuple(remarks))
