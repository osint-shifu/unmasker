"""What a file says about itself, and what kind of thing each field is.

`filetrail` reads these same fields, and more containers than this does. It
answers a different question with them - *where did this file come from* - and
reports each as an origin claim. `/data/filetrail/src/filetrail/sources/
embedded/documents.py` is the implementation, and it was read before this one
was written, as `CLAUDE.md` requires. Two things were taken from it: that dates
have to be normalised out of each container's own format, and that every
property should be kept rather than a chosen few, because no fixed list
anticipates which one an investigation will want.

What is different here is the roles.

## The name of a field is evidence

`CLAUDE.md` sets out the worked example. `LibreOffice/24.2.7.2$Linux_X86_64`
contains a dotted quad; pattern-matching alone reports an IP address; the field
is called `Application`, so it is a version. Context you already have beats a
cleverer pattern.

So every field carries a **role**, decided by its name *and its container*, and
the role decides what may be said about it:

    tool      what produced the file. Never a finding: every PDF has a
              Producer, and a tool that fired on those would exit non-zero on
              every document ever written.
    content   something a person put there - a name, a title, a client, a
              codename. A finding when the document does not show it.
    time      a timestamp, normalised. A finding only when two of them
              contradict each other.
    count     revisions, editing minutes, page counts. Context, not a finding.
    other     read, kept, and not reasoned about.

The container matters as much as the name: a PDF's `/Creator` is the
application that made the original document, and an OOXML `dc:creator` is a
person. One name, two meanings.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from xml.etree import ElementTree

from .xmp import parse_xmp

__all__ = ["Field", "Metadata", "read_odf", "read_ooxml", "read_pdf"]

# Roles, per container. A name absent from these tables is `other`: read and
# kept, and nothing claimed about it.
PDF_ROLES = {
    "producer": "tool",
    "creator": "tool",  # the application, in a PDF
    "author": "content",
    "title": "content",
    "subject": "content",
    "keywords": "content",
    "creationdate": "time",
    "moddate": "time",
    "trapped": "other",
}

OOXML_ROLES = {
    "creator": "content",  # a person, in OOXML
    "lastmodifiedby": "content",
    "title": "content",
    "subject": "content",
    "description": "content",
    "keywords": "content",
    "category": "content",
    "contentstatus": "content",
    "company": "content",
    "manager": "content",
    "template": "content",
    "application": "tool",
    "appversion": "tool",
    "created": "time",
    "modified": "time",
    "lastprinted": "time",
    "revision": "count",
    "totaltime": "count",
    "pages": "count",
    "words": "count",
    "characters": "count",
    "characterswithspaces": "count",
    "paragraphs": "count",
    "lines": "count",
    "language": "other",
}

ODF_ROLES = {
    "initial-creator": "content",
    "creator": "content",
    "title": "content",
    "subject": "content",
    "description": "content",
    "keyword": "content",
    "generator": "tool",
    "creation-date": "time",
    "date": "time",
    "print-date": "time",
    "editing-cycles": "count",
    "editing-duration": "count",
    "language": "other",
    "template": "content",
}

ODF_META = "{urn:oasis:names:tc:opendocument:xmlns:meta:1.0}"
ODF_DC = "{http://purl.org/dc/elements/1.1/}"

CORE = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
EXT = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"


@dataclass(frozen=True)
class Field:
    name: str
    value: str
    part: str
    """Where it was read from: `/Info`, `docProps/core.xml`, and so on. Kept so
    a reader can go and look at the same place."""

    role: str


@dataclass(frozen=True)
class Metadata:
    fields: tuple[Field, ...] = ()
    remarks: tuple[str, ...] = field(default_factory=tuple)

    history: tuple = ()
    """`xmpMM:History` events, for files that carry an XMP packet. An edit
    trail rather than a property: who touched a file and when is one fact about
    the file, so it is kept whole rather than flattened into fields."""

    def where(self, name: str, part: str) -> Field | None:
        """The field with this exact name, from this part of the file.

        Needed because a PDF states its metadata twice and the two do not have
        to agree - which is the most useful thing metadata reading has to say.
        """
        for entry in self.fields:
            if entry.name.lower() == name.lower() and entry.part == part:
                return entry
        return None

    def get(self, name: str) -> Field | None:
        for entry in self.fields:
            if entry.name.lower() == name.lower():
                return entry
        return None

    def by_role(self, role: str) -> tuple[Field, ...]:
        return tuple(entry for entry in self.fields if entry.role == role)


def _clean(value) -> str:
    return str(value).replace("\x00", "").strip() if value is not None else ""


def _pdf_date(value: str) -> str:
    """`D:YYYYMMDDHHmmSS+01'00'` into an ISO timestamp, or back unchanged.

    Unchanged rather than dropped: a date this cannot parse is still what the
    file says, and losing it would be the tool deciding the file had said
    nothing.
    """
    match = re.match(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", value.strip())
    if not match or not match.group(1):
        return value
    parts = [int(g) if g else d for g, d in zip(match.groups(), (0, 1, 1, 0, 0, 0), strict=True)]
    try:
        stamp = datetime(*parts, tzinfo=timezone.utc)
    except ValueError:
        return value
    return stamp.isoformat().replace("+00:00", "Z")


def read_pdf(reader) -> Metadata:
    """Read a PDF's Info dictionary through pypdf.

    `filetrail` scans the raw bytes for these, because it carries no runtime
    dependencies and cannot ask anyone. This project already depends on pypdf
    and the argument for that is written down, so it asks.
    """
    try:
        info = reader.metadata or {}
    except Exception as exc:
        return Metadata(remarks=(f"the Info dictionary could not be read: {exc}",))

    found: list[Field] = []
    for key, raw in info.items():
        name = str(key).lstrip("/")
        value = _clean(raw)
        if not value:
            continue
        role = PDF_ROLES.get(name.lower(), "other")
        if role == "time":
            value = _pdf_date(value)
        found.append(Field(name=name, value=value, part="/Info", role=role))

    packet, remarks = _xmp_packet(reader)
    history: tuple = ()
    if packet:
        xmp_fields, events, problems = parse_xmp(packet)
        found.extend(xmp_fields)
        history = tuple(events)
        remarks.extend(problems)

    return Metadata(fields=tuple(found), remarks=tuple(remarks), history=history)


def _xmp_packet(reader) -> tuple[bytes, list[str]]:
    """The raw XMP bytes, read straight off the catalogue.

    The raw packet rather than pypdf's parsed view of it, because the packet is
    RDF and states one thing four different ways; the parsing that matters is
    in `xmp.py` and needs the XML, not a summary of it.
    """
    try:
        stream = reader.trailer["/Root"].get("/Metadata")
        if stream is None:
            return b"", []
        return stream.get_object().get_data(), []
    except Exception as exc:
        return b"", [f"the XMP packet could not be read: {exc}"]


def _parse(archive: zipfile.ZipFile, member: str):
    try:
        return ElementTree.fromstring(archive.read(member)), None
    except (ElementTree.ParseError, KeyError, OSError) as exc:
        return None, f"{member} could not be parsed and was skipped: {exc}"


def read_ooxml(archive: zipfile.ZipFile) -> Metadata:
    """Read `docProps/core.xml`, `app.xml` and `custom.xml`.

    Custom properties get the `content` role whatever they are called. A
    standard property is something a tool wrote; a custom one is something a
    person put there on purpose, and there is no name table that could
    anticipate them.
    """
    names = set(archive.namelist())
    found: list[Field] = []
    remarks: list[str] = []

    for member in ("docProps/core.xml", "docProps/app.xml"):
        if member not in names:
            continue
        root, problem = _parse(archive, member)
        if problem:
            remarks.append(problem)
            continue
        for child in root:
            name = child.tag.rsplit("}", 1)[-1]
            value = _clean(child.text)
            if not value:
                continue
            found.append(
                Field(
                    name=name,
                    value=value,
                    part=member,
                    role=OOXML_ROLES.get(name.lower(), "other"),
                )
            )

    if "docProps/custom.xml" in names:
        root, problem = _parse(archive, "docProps/custom.xml")
        if problem:
            remarks.append(problem)
        elif root is not None:
            for node in root.iter(f"{{{CUSTOM}}}property"):
                name = node.get("name") or "unnamed"
                value = _clean("".join(child.text or "" for child in node))
                if value:
                    found.append(
                        Field(
                            name=name,
                            value=value,
                            part="docProps/custom.xml",
                            role="content",
                        )
                    )

    return Metadata(fields=tuple(found), remarks=tuple(remarks))


def read_odf(archive: zipfile.ZipFile) -> Metadata:
    """Read `meta.xml` out of an OpenDocument archive.

    ODF's `meta:generator` is the tool - `LibreOffice/24.2.7.2$Linux_X86_64`,
    the same string and the same dotted quad as `docProps/app.xml`, and the
    same answer: the field names a tool, so it is a version.

    `meta:user-defined` is ODF's custom property, and gets the `content` role
    whatever it is called, for the reason OOXML's custom properties do: a
    standard property is something a tool wrote, a custom one is something a
    person put there on purpose, and no name table anticipates them.
    """
    if "meta.xml" not in archive.namelist():
        return Metadata()
    root, problem = _parse(archive, "meta.xml")
    if problem:
        return Metadata(remarks=(problem,))

    found: list[Field] = []
    for child in root.iter():
        name = child.tag.rsplit("}", 1)[-1]
        if name in ("document-meta", "meta"):
            continue
        value = _clean(child.text)
        if not value:
            continue
        if child.tag == f"{ODF_META}user-defined":
            found.append(
                Field(
                    name=child.get(f"{ODF_META}name") or "user-defined",
                    value=value,
                    part="meta.xml",
                    role="content",
                )
            )
            continue
        found.append(
            Field(
                name=name,
                value=value,
                part="meta.xml",
                role=ODF_ROLES.get(name.lower(), "other"),
            )
        )
    return Metadata(fields=tuple(found))
