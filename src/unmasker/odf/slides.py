"""An OpenDocument presentation's slides, and which of them are skipped.

The same indirection this format uses for a hidden spreadsheet sheet, one
container over: **a slide's visibility is not on the slide**. The page names a
style, and the style, elsewhere in the file, says
`presentation:visibility="hidden"`.

    <draw:page draw:name="Cut" draw:style-name="dp3">
    ...
    <style:style style:name="dp3" style:family="drawing-page">
      <style:drawing-page-properties presentation:visibility="hidden"/>

A reader that looks for an attribute on the page finds nothing and reports a
deck with a cut slide as clean. Having met it once in `odf/sheets.py` is the
only reason it was expected here.

Notes sit inside the slide they belong to, in `<presentation:notes>`, which is
the same shape as an annotation inside a paragraph and carries the same trap:
walking the subtree naively puts the speaker's private line into the text of
the slide itself.

No new dependency: an .odp is a zip of XML and both are in the standard
library.
"""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from ..slides import Slide, SlideRecord

OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
DRAW = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"
PRESENTATION = "{urn:oasis:names:tc:opendocument:xmlns:presentation:1.0}"
STYLE = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def _hidden_styles(root) -> set[str]:
    """Style names whose pages are skipped. The indirection this reader exists
    for."""
    names = set()
    for container in (f"{OFFICE}automatic-styles", f"{OFFICE}styles"):
        for holder in root.iter(container):
            for style in holder.iter(f"{STYLE}style"):
                if style.get(f"{STYLE}family") != "drawing-page":
                    continue
                for props in style.iter(f"{STYLE}drawing-page-properties"):
                    if (props.get(f"{PRESENTATION}visibility") or "").strip() == "hidden":
                        name = style.get(f"{STYLE}name")
                        if name:
                            names.add(name)
    return names


def _paragraphs(node, skip: set[int]) -> list[str]:
    out = []
    for paragraph in node.iter(f"{TEXT}p"):
        if id(paragraph) in skip:
            continue
        text = "".join(paragraph.itertext()).strip()
        if text:
            out.append(text)
    return out


def _read_page(page, hidden: bool, number: int) -> Slide:
    # The notes subtree is taken out of the slide's own text first. Walking it
    # naively puts the speaker's private line into what the audience saw.
    notes_nodes = list(page.iter(f"{PRESENTATION}notes"))
    inside_notes = {id(n) for node in notes_nodes for n in node.iter()}

    on_screen = _paragraphs(page, inside_notes)
    spoken: list[str] = []
    for node in notes_nodes:
        spoken.extend(_paragraphs(node, set()))

    return Slide(
        number=number,
        text="\n".join(on_screen),
        notes="\n".join(spoken),
        hidden=hidden,
        title=on_screen[0] if on_screen else page.get(f"{DRAW}name"),
    )


def read_slides(archive: zipfile.ZipFile) -> SlideRecord:
    if "content.xml" not in archive.namelist():
        return SlideRecord(remarks=("the file has no content.xml and was not read",))

    try:
        root = ElementTree.fromstring(archive.read("content.xml"))
    except ElementTree.ParseError as exc:
        return SlideRecord(remarks=(f"content.xml is not well-formed XML: {exc}",))

    invisible = _hidden_styles(root)

    slides: list[Slide] = []
    for body in root.iter(f"{OFFICE}presentation"):
        for page in body.iter(f"{DRAW}page"):
            hidden = (page.get(f"{DRAW}style-name") or "") in invisible
            slides.append(_read_page(page, hidden, len(slides) + 1))

    return SlideRecord(slides=tuple(slides))
