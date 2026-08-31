"""The XMP packet: the second place a PDF states its metadata.

A PDF says who made it twice, in the Info dictionary and in an XMP packet, and
nothing in the format makes the two agree. Tools that "remove metadata"
routinely clear one and leave the other, so a document arrives with a scrubbed
Info dictionary - the place anybody checking will look - and a packet still
holding the author, the working title and the trail of every application that
has touched the file.

## RDF says one thing four ways

The packet is RDF/XML, and a property can be written as

    a bare text element        <xmpMM:OriginalDocumentID>uuid:…</…>
    an ordered list            <dc:creator><rdf:Seq><rdf:li>…</rdf:li></rdf:Seq></…>
    a language alternative     <dc:title><rdf:Alt><rdf:li xml:lang='x-default'>…
    a nested structure         <…:CreatorContactInfo rdf:parseType='Resource'>…
    an XML attribute           <rdf:Description pdf:Producer='…' />

All five are handled. The last one matters more than it looks: Adobe writes
whole packets in attribute form, nothing this repository produces does, and a
parser tested only against its own specimens would not support it and would not
notice.

## What is not flattened

`xmpMM:History` is an edit trail rather than a property, and it comes back as
events. Who touched a file and when is one fact about the file - the same rule
the DOCX revision history follows, arriving in a different container.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
XML = "{http://www.w3.org/XML/1998/namespace}"

# Prefixes for the namespaces a packet actually uses, so a field can be named
# `dc:creator` rather than by a URL nobody reads.
PREFIXES = {
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://ns.adobe.com/pdf/1.3/": "pdf",
    "http://ns.adobe.com/xap/1.0/": "xmp",
    "http://ns.adobe.com/xap/1.0/mm/": "xmpMM",
    "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#": "stEvt",
    "http://ns.adobe.com/xap/1.0/sType/ResourceRef#": "stRef",
    "http://ns.adobe.com/xap/1.0/t/pg/": "xmpTPg",
    "http://ns.adobe.com/photoshop/1.0/": "photoshop",
    "http://ns.adobe.com/xap/1.0/rights/": "xmpRights",
    "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/": "Iptc4xmpCore",
    "http://iptc.org/std/Iptc4xmpExt/2008-02-29/": "Iptc4xmpExt",
    "http://purl.org/dc/terms/": "dcterms",
    "http://www.aiim.org/pdfa/ns/id/": "pdfaid",
    "adobe:ns:meta/": "x",
}

CONTAINERS = (f"{RDF}Seq", f"{RDF}Bag", f"{RDF}Alt")


@dataclass(frozen=True)
class HistoryEvent:
    """One entry of `xmpMM:History`: something that happened to the file."""

    action: str | None = None
    software: str | None = None
    when: str | None = None
    changed: str | None = None
    instance: str | None = None

    def described(self) -> str:
        parts = [self.action or "an unnamed action"]
        if self.software:
            parts.append(f"by {self.software}")
        if self.when:
            parts.append(f"on {self.when}")
        if self.changed and self.changed not in ("/",):
            parts.append(f"touching {self.changed}")
        return " ".join(parts)


def _split(tag: str) -> tuple[str, str]:
    """A namespaced tag into (prefix, local name)."""
    if not tag.startswith("{"):
        return "", tag
    namespace, local = tag[1:].split("}", 1)
    return PREFIXES.get(namespace, namespace.rstrip("/#").rsplit("/", 1)[-1]), local


def _qualified(tag: str) -> str:
    prefix, local = _split(tag)
    return f"{prefix}:{local}" if prefix else local


def _container_values(node) -> list[str] | None:
    """The `rdf:li` values of a Seq, Bag or Alt, or None if this is not one."""
    for child in node:
        if child.tag in CONTAINERS:
            return [
                (item.text or "").strip()
                for item in child
                if item.tag == f"{RDF}li" and (item.text or "").strip()
            ]
    return None


def _is_structure(node) -> bool:
    if node.get(f"{RDF}parseType") == "Resource":
        return True
    return any(child.tag == f"{RDF}Description" for child in node)


def _structure_children(node):
    for child in node:
        if child.tag == f"{RDF}Description":
            yield from child
        elif child.tag not in CONTAINERS:
            yield child


def _history(node) -> list[HistoryEvent]:
    events: list[HistoryEvent] = []
    for container in node:
        if container.tag not in CONTAINERS:
            continue
        for item in container:
            if item.tag != f"{RDF}li":
                continue
            values = {}
            for field in item:
                _, local = _split(field.tag)
                values[local.lower()] = (field.text or "").strip()
            for key, value in item.attrib.items():
                _, local = _split(key)
                if not key.startswith(RDF):
                    values.setdefault(local.lower(), value.strip())
            events.append(
                HistoryEvent(
                    action=values.get("action") or None,
                    software=values.get("softwareagent") or None,
                    when=values.get("when") or None,
                    changed=values.get("changed") or None,
                    instance=values.get("instanceid") or None,
                )
            )
    return events


def _property(child, prefix: str, out: list[tuple[str, str]]) -> None:
    """Collect (name, value) for one property element, whatever form it takes."""
    name = _qualified(child.tag)
    full = f"{prefix}/{_split(child.tag)[1]}" if prefix else name

    values = _container_values(child)
    if values is not None:
        if values:
            out.append((full, "; ".join(values)))
        return

    if _is_structure(child):
        _walk_structure(child, full, out)
        return

    text = (child.text or "").strip()
    if text:
        out.append((full, text))

    for key, value in child.attrib.items():
        if key.startswith(RDF) or key.startswith(XML) or not value.strip():
            continue
        out.append((f"{full}/{_split(key)[1]}", value.strip()))


def _walk_structure(node, name: str, out: list[tuple[str, str]]) -> None:
    for field in _structure_children(node):
        text = (field.text or "").strip()
        if text:
            out.append((f"{name}/{_split(field.tag)[1]}", text))
    for key, value in node.attrib.items():
        if key.startswith(RDF) or key.startswith(XML):
            continue
        out.append((f"{name}/{_split(key)[1]}", value.strip()))


def parse_xmp(raw: bytes) -> tuple[list, list[HistoryEvent], list[str]]:
    """Read a packet into (fields, history, remarks).

    `fields` are `(name, value)` pairs; the caller assigns roles, because the
    role table lives with the other containers' and is what keeps a version
    string out of the findings.

    Never raises. A packet that will not parse costs itself and nothing else,
    and says so: a forensic tool is pointed at damaged files on purpose.
    """
    from . import Field

    if not raw or not raw.strip():
        return [], [], []

    # A packet is wrapped in <?xpacket?> processing instructions and padded
    # with whitespace, both of which are legal and neither of which ElementTree
    # wants outside the root element.
    text = raw.decode("utf-8", "replace")
    start = text.find("<x:xmpmeta")
    if start < 0:
        start = text.find("<rdf:RDF")
    end = text.rfind("</x:xmpmeta>")
    if end < 0:
        end = text.rfind("</rdf:RDF>")
        end = end + len("</rdf:RDF>") if end >= 0 else -1
    else:
        end += len("</x:xmpmeta>")
    if start < 0 or end < 0:
        return [], [], ["the XMP packet holds no RDF and was not read"]

    try:
        root = ElementTree.fromstring(text[start:end])
    except ElementTree.ParseError as exc:
        return [], [], [f"the XMP packet is not well-formed XML and was not read: {exc}"]

    pairs: list[tuple[str, str]] = []
    history: list[HistoryEvent] = []

    for description in root.iter(f"{RDF}Description"):
        # Properties written as attributes. Adobe writes whole packets this way.
        for key, value in description.attrib.items():
            if key.startswith(RDF) or key.startswith(XML) or not value.strip():
                continue
            pairs.append((_qualified(key), value.strip()))

        for child in description:
            _, local = _split(child.tag)
            if local == "History":
                # An edit trail, not a property. Who touched a file and when is
                # one fact about the file, so it is kept whole.
                history.extend(_history(child))
                continue
            _property(child, "", pairs)

    seen: set[tuple[str, str]] = set()
    fields = []
    for name, value in pairs:
        if not value or (name, value) in seen:
            continue
        seen.add((name, value))
        fields.append(Field(name=name, value=value, part="XMP", role=role_of(name)))

    return fields, history, []


# Roles for XMP, keyed on the flattened name and then on its last segment. The
# same rule as everywhere else: the name of a field is evidence, and a version
# string in a tool field is a version whatever it looks like.
XMP_ROLES = {
    "producer": "tool",
    "creatortool": "tool",
    "xmptk": "tool",
    "creator": "content",
    "title": "content",
    "description": "content",
    "subject": "content",
    "rights": "content",
    "keywords": "content",
    "createdate": "time",
    "modifydate": "time",
    "metadatadate": "time",
    "format": "other",
    "documentid": "other",
    "instanceid": "other",
    "renditionclass": "other",
    "versionid": "other",
    "originaldocumentid": "content",
    "derivedfrom/documentid": "content",
    "derivedfrom/originaldocumentid": "content",
    "derivedfrom/instanceid": "content",
}

# Namespaces whose every property describes a person or an organisation.
PERSONAL = ("iptc4xmpcore", "iptc4xmpext", "photoshop", "xmprights")


def role_of(name: str) -> str:
    """What kind of thing this XMP property is."""
    lowered = name.lower()
    bare = lowered.split(":", 1)[-1]
    if bare in XMP_ROLES:
        return XMP_ROLES[bare]
    if lowered.split(":", 1)[0] in PERSONAL:
        return "content"
    last = bare.rsplit("/", 1)[-1]
    return XMP_ROLES.get(last, "other")
