"""Tracked changes and comments in an OpenDocument file.

Same statements as OOXML's, in a different vocabulary. `<text:deletion>` holds
the struck-out text where Word holds it in `w:delText`, and
`<office:annotation>` is a comment where Word puts one in a separate part of
the zip. The record and the findings are shared - see `unmasker.revisions` -
because a deletion is a fact about a document rather than about a file format.

## The thing that must not be got wrong

Both of these live **inside the body text** in ODF, not in a separate part.
`<text:tracked-changes>` sits at the top of `office:text` and
`<office:annotation>` sits inline in the paragraph it belongs to. So the text
reader has to walk around them: extracting the body naively would report the
deleted sentence and the comment as ordinary visible prose, which is precisely
backwards - the whole point is that a reader of the page sees neither.

## Insertions

ODF records an insertion as a region holding only its change-info; the inserted
words stay in the body between a `text:change-start` and a `text:change-end`.
They are on the page, so this reads the authorship and not the text - which is
the same treatment `w:ins` gets, arrived at from the other direction.
"""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from ..revisions import Comment, Revision, RevisionRecord

TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
DC = "{http://purl.org/dc/elements/1.1/}"

# Regions that take text off the page, and what each becomes.
HIDING = {f"{TEXT}deletion": "deletion"}
SHOWING = {f"{TEXT}insertion": "insertion"}
FORMATTING = {f"{TEXT}format-change"}

PARTS = ("content.xml", "styles.xml")


def _text_under(node, skip=()) -> str:
    """Every character under `node`, minus the subtrees named in `skip`."""
    out: list[str] = []

    def walk(element) -> None:
        for child in element:
            if child.tag in skip:
                if child.tail:
                    out.append(child.tail)
                continue
            if child.tag == f"{TEXT}s":
                out.append(" " * int(child.get(f"{TEXT}c", "1") or 1))
            elif child.tag == f"{TEXT}tab":
                out.append("\t")
            elif child.tag == f"{TEXT}line-break":
                out.append("\n")
            if child.text:
                out.append(child.text)
            walk(child)
            if child.tail:
                out.append(child.tail)

    if node.text:
        out.append(node.text)
    walk(node)
    return "".join(out)


def _change_info(region):
    info = region.find(f".//{OFFICE}change-info")
    if info is None:
        return None, None
    author = info.findtext(f"{DC}creator")
    date = info.findtext(f"{DC}date")
    return (author.strip() if author else None), (date.strip() if date else None)


def _revisions_in(root, part: str) -> tuple[list[Revision], bool]:
    found: list[Revision] = []
    formatting = False
    for region in root.iter(f"{TEXT}changed-region"):
        for kind_node in region:
            if kind_node.tag in FORMATTING:
                formatting = True
                continue
            kind = HIDING.get(kind_node.tag) or SHOWING.get(kind_node.tag)
            if kind is None:
                continue
            author, date = _change_info(region)
            # The change-info is metadata about the region, not its content.
            text = _text_under(kind_node, skip=(f"{OFFICE}change-info",))
            found.append(
                Revision(
                    kind=kind,
                    text=text.strip(),
                    author=author,
                    date=date,
                    part=part,
                )
            )
    return found, formatting


def _comments_in(root) -> list[Comment]:
    out = []
    for node in root.iter(f"{OFFICE}annotation"):
        author = node.findtext(f"{DC}creator")
        date = node.findtext(f"{DC}date")
        text = _text_under(node, skip=(f"{DC}creator", f"{DC}date"))
        out.append(
            Comment(
                text=text.strip(),
                author=author.strip() if author else None,
                date=date.strip() if date else None,
            )
        )
    return out


def read_revisions(archive: zipfile.ZipFile) -> RevisionRecord:
    """Read every tracked change and comment out of an open .odt archive.

    Never raises on a damaged part. A `styles.xml` that will not parse costs
    its own revisions and nothing else, and says so.
    """
    names = set(archive.namelist())
    revisions: list[Revision] = []
    comments: list[Comment] = []
    remarks: list[str] = []
    formatting = False

    for part in PARTS:
        if part not in names:
            continue
        try:
            root = ElementTree.fromstring(archive.read(part))
        except (ElementTree.ParseError, KeyError, OSError) as exc:
            remarks.append(f"{part} could not be parsed and was skipped: {exc}")
            continue
        found, saw = _revisions_in(root, part)
        revisions.extend(found)
        comments.extend(_comments_in(root))
        formatting = formatting or saw

    if formatting:
        remarks.append(
            "the file records tracked formatting changes; they carry an author "
            "but no hidden text, so they are counted nowhere and reported nowhere"
        )

    return RevisionRecord(
        revisions=tuple(revisions),
        comments=tuple(comments),
        remarks=tuple(remarks),
    )
