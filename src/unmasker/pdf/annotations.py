"""Annotations: what hangs off a page without being on it.

A comment in a PDF is a dictionary attached to the page. The text is in
`/Contents`, the author in `/T`, and none of it is part of the page: it does not
print, `pdftotext` does not report it, and a reader looking at the document
never meets it. Every PDF library reads it in one line.

This was a blind spot rather than a gap in the specimens. The interpreter read
the page's content stream and never looked at `/Annots` at all, so no amount of
content-stream work would ever have found a comment - the same class of miss as
reading only the Info dictionary and never the XMP packet.

## The one subtype that is not a gap

`/FreeText` draws its contents on the page. A reader sees exactly what a parser
gets, and reporting it would be the tool calling the visible document a
concealment. It is read and not reported, and the distinction is a test.

## What is not read

Appearance streams. An annotation may carry an `/AP` form that paints anything
at all, including a black rectangle over text, and nothing here interprets one.
That is a real technique and it needs a producer this machine does not have -
`tests/specimens/README.md` names it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Subtypes whose `/Contents` is a note *about* the page rather than text drawn
# *on* it. `/FreeText` is deliberately absent; `/Popup` and `/Link` carry no
# note of their own.
NOTE_SUBTYPES = frozenset(
    {
        "Text",
        "Highlight",
        "Underline",
        "StrikeOut",
        "Squiggly",
        "Square",
        "Circle",
        "Line",
        "Polygon",
        "PolyLine",
        "Ink",
        "Stamp",
        "Caret",
        "FileAttachment",
        "Sound",
        "Movie",
        "Redact",
    }
)


@dataclass(frozen=True)
class Annotation:
    subtype: str
    contents: str = ""
    author: str = ""
    modified: str = ""
    has_appearance: bool = False
    """Whether it carries an `/AP` form. Nothing interprets one yet, so this is
    what a remark would be built from rather than something acted on."""

    @property
    def is_a_note(self) -> bool:
        return self.subtype in NOTE_SUBTYPES and bool(self.contents.strip())


def _text(value) -> str:
    if value is None:
        return ""
    try:
        value = value.get_object()
    except AttributeError:
        pass
    return str(value).replace("\x00", "").strip().rstrip(",").strip()


def read_annotations(page) -> list[Annotation]:
    """Every annotation on `page`, in the order the file lists them.

    Never raises. A page in a damaged file can hold anything at all in
    `/Annots`, and losing every annotation because one entry is not a
    dictionary would turn damage into silence.
    """
    try:
        raw = page.get("/Annots")
        if raw is None:
            return []
        raw = raw.get_object() if hasattr(raw, "get_object") else raw
        entries = list(raw)
    except Exception:
        return []

    found: list[Annotation] = []
    for entry in entries:
        try:
            item = entry.get_object() if hasattr(entry, "get_object") else entry
            subtype = _text(item.get("/Subtype")).lstrip("/")
            found.append(
                Annotation(
                    subtype=subtype,
                    contents=_text(item.get("/Contents")),
                    author=_text(item.get("/T")),
                    modified=_text(item.get("/M")),
                    has_appearance="/AP" in item,
                )
            )
        except Exception:
            continue
    return found
