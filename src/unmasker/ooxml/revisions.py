"""Tracked changes and comments, read out of a Word document.

A tracked deletion removes nothing. The struck-out run stays in the file as
`w:delText`, beside the name of whoever deleted it and the minute they did, and
a reader whose review pane shows the final text sees none of it. Word calls
that a deletion; the file calls it a paragraph with more in it than the page
shows.

## What is a deletion and what is not

`w:del` and `w:moveFrom` take text off the page and leave it in the file. Those
are hidden text.

`w:ins` and `w:moveTo` put text *on* the page. Nothing about the words is
hidden, and reporting them as concealment would be wrong. What they do conceal
is who wrote them and when, which is one fact about the document rather than
one fact per insertion - so it is gathered here and reported once.

`w:rPrChange` and `w:pPrChange` record that someone changed a font or an
indent. They carry an author and no text at all. They are remarked on and not
reported, because a finding that quotes nothing teaches a reader to skip
findings.

## No new dependency

A .docx is a zip of XML and both are in the standard library. This project
requires a second dependency to be argued for in writing, and there is no
argument to make here.
"""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from ..revisions import Comment, Revision, RevisionRecord

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Revision elements that take text off the page, and the kind each becomes.
HIDING = {f"{W}del": "deletion", f"{W}moveFrom": "move-from"}
SHOWING = {f"{W}ins": "insertion", f"{W}moveTo": "move-to"}
REVISION_TAGS = {**HIDING, **SHOWING}

FORMATTING_TAGS = {f"{W}rPrChange", f"{W}pPrChange", f"{W}tblPrChange", f"{W}tcPrChange"}


def _parts(archive: zipfile.ZipFile) -> list[str]:
    """The body first, then headers and footers, in a stable order.

    Revisions live in headers and footers too, and a reader who was told a
    document had none because only the body was checked has been told something
    untrue.
    """
    names = set(archive.namelist())
    ordered = ["word/document.xml"] if "word/document.xml" in names else []
    ordered += sorted(
        n for n in names if n.startswith(("word/header", "word/footer")) and n.endswith(".xml")
    )
    return ordered


def _text_under(node) -> str:
    """Every character the element covers, from both `w:t` and `w:delText`.

    Both are needed: a deletion nested inside another holds its text in
    `w:delText`, while an insertion that was later deleted keeps it in `w:t`.
    """
    out = []
    for child in node.iter():
        if child.tag in (f"{W}t", f"{W}delText"):
            out.append(child.text or "")
        elif child.tag == f"{W}tab":
            out.append("\t")
        elif child.tag == f"{W}br":
            out.append("\n")
    return "".join(out)


def _revisions_in(root, part: str) -> tuple[list[Revision], bool]:
    """Every outermost revision element in one part, and whether any formatting
    change was seen."""
    parents = {child: parent for parent in root.iter() for child in parent}

    def inside_a_revision(node) -> bool:
        cursor = parents.get(node)
        while cursor is not None:
            if cursor.tag in REVISION_TAGS:
                return True
            cursor = parents.get(cursor)
        return False

    found: list[Revision] = []
    formatting = False
    for node in root.iter():
        if node.tag in FORMATTING_TAGS:
            formatting = True
            continue
        kind = REVISION_TAGS.get(node.tag)
        if kind is None or inside_a_revision(node):
            continue
        found.append(
            Revision(
                kind=kind,
                text=_text_under(node),
                author=node.get(f"{W}author"),
                date=node.get(f"{W}date"),
                part=part,
            )
        )
    return found, formatting


def _comments_in(archive: zipfile.ZipFile) -> tuple[list[Comment], list[str]]:
    if "word/comments.xml" not in archive.namelist():
        return [], []
    try:
        root = ElementTree.fromstring(archive.read("word/comments.xml"))
    except (ElementTree.ParseError, KeyError) as exc:
        return [], [f"word/comments.xml could not be read: {exc}"]

    out = []
    for node in root.iter(f"{W}comment"):
        out.append(
            Comment(
                text=_text_under(node),
                author=node.get(f"{W}author"),
                date=node.get(f"{W}date"),
                initials=node.get(f"{W}initials") or None,
            )
        )
    return out, []


def read_revisions(archive: zipfile.ZipFile) -> RevisionRecord:
    """Read every tracked change and comment out of an open .docx archive.

    Never raises on a damaged part. A header that will not parse costs its own
    revisions and nothing else, and says so in a remark - losing the whole
    document because one part is malformed would turn damage into silence.
    """
    revisions: list[Revision] = []
    remarks: list[str] = []
    formatting = False

    for part in _parts(archive):
        try:
            root = ElementTree.fromstring(archive.read(part))
        except (ElementTree.ParseError, KeyError) as exc:
            remarks.append(f"{part} could not be parsed and was skipped: {exc}")
            continue
        found, saw_formatting = _revisions_in(root, part)
        revisions.extend(found)
        formatting = formatting or saw_formatting

    comments, comment_remarks = _comments_in(archive)
    remarks.extend(comment_remarks)

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
