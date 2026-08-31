"""XMP: the second place a PDF states its metadata, and the one that survives.

A PDF says who made it twice - once in the Info dictionary and once in an XMP
packet - and nothing in the format makes the two agree. Tools that "remove
metadata" routinely clear one and not the other, so the document arrives with a
scrubbed Info dictionary, which is where anybody checking will look, and a
packet that still holds the author, the working title and the trail of every
application that has touched the file.

That is what `xmp-survives-the-scrub.pdf` is, and it is the strongest thing
metadata reading adds: not another field dump, but *the two halves of one file
disagreeing about what the file is*.

The parsing has to cope with RDF, which states the same thing four ways: a bare
text property, an `rdf:Alt` or `rdf:Seq` of `rdf:li`, a nested structure under
`rdf:parseType='Resource'`, and a property written as an XML attribute on
`rdf:Description`. Adobe writes the last of those constantly and nothing in
this repository's own specimens does, so it has its own tests.
"""

import pytest
from conftest import SPECIMENS
from pypdf import PdfReader

from unmasker.findings import Basis
from unmasker.metadata import read_pdf
from unmasker.metadata.detectors import detect
from unmasker.metadata.xmp import parse_xmp

SPECIMEN = SPECIMENS / "pdf" / "xmp-survives-the-scrub.pdf"
VISIBLE = "The company will not be commenting further at this time."

HEAD = (
    "<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
    "<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
    "<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
)
TAIL = "</rdf:RDF></x:xmpmeta><?xpacket end='w'?>"


def packet(body: str) -> bytes:
    return (HEAD + body + TAIL).encode("utf-8")


def named(fields, name):
    for entry in fields:
        if entry.name.lower().endswith(name.lower()):
            return entry
    return None


def meta_of(path=SPECIMEN):
    return read_pdf(PdfReader(str(path)))


# --------------------------------------------------------------------------
# the four ways RDF says one thing
# --------------------------------------------------------------------------


def test_a_bare_text_property():
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:xmpMM='http://ns.adobe.com/xap/1.0/mm/'>"
            "<xmpMM:OriginalDocumentID>uuid:1234</xmpMM:OriginalDocumentID>"
            "</rdf:Description>"
        )
    )
    assert named(fields, "OriginalDocumentID").value == "uuid:1234"


def test_an_rdf_seq_of_one():
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            "<dc:creator><rdf:Seq><rdf:li>Halina Nowak-Test</rdf:li></rdf:Seq></dc:creator>"
            "</rdf:Description>"
        )
    )
    assert named(fields, "creator").value == "Halina Nowak-Test"


def test_an_rdf_seq_of_several_keeps_all_of_them():
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            "<dc:creator><rdf:Seq><rdf:li>One Person</rdf:li>"
            "<rdf:li>Another Person</rdf:li></rdf:Seq></dc:creator>"
            "</rdf:Description>"
        )
    )
    value = named(fields, "creator").value
    assert "One Person" in value and "Another Person" in value


def test_an_rdf_alt_with_a_language_qualifier():
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            "<dc:title><rdf:Alt><rdf:li xml:lang='x-default'>Working title</rdf:li>"
            "</rdf:Alt></dc:title></rdf:Description>"
        )
    )
    assert named(fields, "title").value == "Working title"


def test_a_property_written_as_an_attribute():
    """Adobe writes whole packets this way. Nothing this project produces does,
    so without this test the form would be untested and silently unsupported."""
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:pdf='http://ns.adobe.com/pdf/1.3/' "
            "xmlns:xmp='http://ns.adobe.com/xap/1.0/' "
            "pdf:Producer='Acrobat Distiller 24.0' xmp:CreatorTool='InDesign 19.0'/>"
        )
    )
    assert named(fields, "Producer").value == "Acrobat Distiller 24.0"
    assert named(fields, "CreatorTool").value == "InDesign 19.0"


def test_a_nested_structure_is_flattened_under_its_parent():
    fields, _, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' "
            "xmlns:Iptc4xmpCore='http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/'>"
            "<Iptc4xmpCore:CreatorContactInfo rdf:parseType='Resource'>"
            "<Iptc4xmpCore:CiEmailWork>h.nowak@example.org</Iptc4xmpCore:CiEmailWork>"
            "</Iptc4xmpCore:CreatorContactInfo></rdf:Description>"
        )
    )
    entry = named(fields, "CiEmailWork")
    assert entry.value == "h.nowak@example.org"
    assert "CreatorContactInfo" in entry.name


def test_the_rdf_bookkeeping_attributes_are_not_properties():
    """`rdf:about` and the namespace declarations are how RDF is written, not
    something anybody put in the file."""
    fields, _, _ = parse_xmp(
        packet("<rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'/>")
    )
    assert fields == []


# --------------------------------------------------------------------------
# the history
# --------------------------------------------------------------------------


def test_the_history_is_read_as_events_rather_than_flattened_fields():
    _, history, _ = parse_xmp(
        packet(
            "<rdf:Description rdf:about='' xmlns:xmpMM='http://ns.adobe.com/xap/1.0/mm/' "
            "xmlns:stEvt='http://ns.adobe.com/xap/1.0/sType/ResourceEvent#'>"
            "<xmpMM:History><rdf:Seq>"
            "<rdf:li rdf:parseType='Resource'><stEvt:action>created</stEvt:action>"
            "<stEvt:softwareAgent>InDesign 19.0</stEvt:softwareAgent>"
            "<stEvt:when>2024-01-02T09:00:00Z</stEvt:when></rdf:li>"
            "<rdf:li rdf:parseType='Resource'><stEvt:action>saved</stEvt:action>"
            "<stEvt:softwareAgent>Acrobat 24.0</stEvt:softwareAgent>"
            "<stEvt:when>2024-04-19T16:41:00Z</stEvt:when></rdf:li>"
            "</rdf:Seq></xmpMM:History></rdf:Description>"
        )
    )
    assert len(history) == 2
    assert [event.action for event in history] == ["created", "saved"]
    assert history[1].software == "Acrobat 24.0"


def test_the_history_becomes_one_finding_not_one_per_event():
    meta = meta_of()
    assert len(meta.history) == 2, "the specimen carries a trail, not a single event"
    found = [f for f in detect(meta, VISIBLE) if f.detector == "revision-history"]
    assert len(found) == 1
    assert found[0].basis is Basis.SELF_REPORTED
    assert "Acrobat Distiller" in found[0].machine_reads


def test_the_history_events_come_back_in_the_order_the_file_lists_them():
    """A trail is a sequence. Read out of order it says the file was created
    after it was distilled."""
    events = meta_of().history
    assert [e.action for e in events] == ["created", "saved"]
    assert "InDesign" in events[0].software
    assert "Distiller" in events[1].software


def test_both_applications_are_named_in_the_finding():
    (found,) = [f for f in detect(meta_of(), VISIBLE) if f.detector == "revision-history"]
    assert "InDesign" in found.machine_reads
    assert "Distiller" in found.machine_reads
    assert "2 events" in found.summary


def test_a_file_with_no_history_gets_no_history_finding():
    meta = meta_of(SPECIMENS / "pdf" / "libreoffice-writer-black-bars.pdf")
    assert not any(f.detector == "revision-history" for f in detect(meta, "text"))


# --------------------------------------------------------------------------
# the disagreement
# --------------------------------------------------------------------------


def test_the_scrubbed_title_and_the_working_title_are_reported_as_a_conflict():
    """The Info dictionary says `Statement`. The XMP packet says
    `Statement - HOLD until legal clears`. One file, two answers."""
    found = [f for f in detect(meta_of(), VISIBLE) if f.detector == "metadata-conflict"]
    assert len(found) == 1
    assert "HOLD until legal clears" in found[0].machine_reads
    assert "Statement" in found[0].summary


def test_the_pdf_subject_is_compared_against_dc_description_not_dc_subject():
    """The PDF specification maps `/Subject` onto `dc:description`, and
    `dc:subject` onto `/Keywords`. Pairing them by name would compare two
    fields that mean different things and report a conflict that is not one."""
    from unmasker.metadata import Field, Metadata

    meta = Metadata(
        fields=(
            Field("Subject", "A short abstract", "/Info", "content"),
            Field("dc:description", "A short abstract", "XMP", "content"),
            Field("dc:subject", "keyword; keyword", "XMP", "content"),
        )
    )
    assert not any(f.detector == "metadata-conflict" for f in detect(meta, "unrelated"))


def test_a_value_present_in_only_one_of_the_two_is_not_a_conflict():
    """XMP holding an author the Info dictionary lacks is XMP holding more, not
    the file contradicting itself. It is reported, as undisclosed metadata."""
    found = detect(meta_of(), VISIBLE)
    creator = [f for f in found if "Halina Nowak-Test" in f.machine_reads]
    assert len(creator) == 1
    assert creator[0].detector == "undisclosed-metadata"


def test_tool_fields_that_disagree_are_not_reported():
    """`/Creator` is `Writer` and `xmp:CreatorTool` is the full LibreOffice
    build string. They are a listed pair, they disagree, and neither is
    reported: both are true, both name a tool, and files say two things about
    that constantly."""
    meta = meta_of()
    assert meta.where("Creator", "/Info").value == "Writer"
    assert meta.where("xmp:CreatorTool", "XMP").value.startswith("LibreOffice/")
    found = detect(meta, VISIBLE)
    assert not any("CreatorTool" in f.summary for f in found)
    assert not any(
        f.detector == "metadata-conflict" and "Creator" in f.summary and "Title" not in f.summary
        for f in found
    )


# --------------------------------------------------------------------------
# the specimen, whole
# --------------------------------------------------------------------------


def test_the_scrub_looks_complete_in_the_info_dictionary():
    """The premise. Anybody checking the obvious place sees a clean file."""
    info = PdfReader(str(SPECIMEN)).metadata or {}
    assert "/Author" not in info
    assert "/Subject" not in info
    assert "/Keywords" not in info
    assert info.get("/Title") == "Statement"


def test_everything_the_scrub_missed_is_reported():
    reads = " | ".join(f.machine_reads for f in detect(meta_of(), VISIBLE))
    for survived in (
        "Halina Nowak-Test",
        "Statement - HOLD until legal clears",
        "Do not release before the settlement is signed.",
        "h.nowak@example.org",
        "uuid:3c9f77e0-0000-4000-8000-000000000001",
    ):
        assert survived in reads, survived


def test_the_info_dictionary_and_the_packet_are_both_in_the_record():
    parts = {entry.part for entry in meta_of().fields}
    assert parts == {"/Info", "XMP"}


def test_the_creator_tool_version_is_still_not_read_as_an_address():
    """`xmp:CreatorTool` here is `LibreOffice/24.2.7.2$Linux_X86_64`. The same
    rule holds in XMP as in `docProps/app.xml`: the field names a tool."""
    entry = named(meta_of().fields, "CreatorTool")
    assert "24.2.7.2" in entry.value
    assert entry.role == "tool"
    assert not any("24.2.7.2" in f.machine_reads for f in detect(meta_of(), VISIBLE))


def test_a_lineage_identifier_is_explained_rather_than_left_as_a_uuid():
    """`the xmpMM:OriginalDocumentID field holds a value the document does not
    show` is true and useless. It names the document this one was made from,
    and saying so is the same principle as the rest: the name of a field is
    evidence, so use it."""
    found = detect(meta_of(), VISIBLE)
    original = next(f for f in found if "000000000001" in f.machine_reads)
    assert "made from" in original.summary
    derived = next(f for f in found if "000000000002" in f.machine_reads)
    assert "derived from" in derived.summary


def test_an_ordinary_field_gets_no_invented_explanation():
    found = detect(meta_of(), VISIBLE)
    creator = next(f for f in found if "Halina" in f.machine_reads)
    assert creator.summary.endswith("anywhere in its text")


# --------------------------------------------------------------------------
# damage
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not xml at all",
        b"<x:xmpmeta>unclosed",
        b"\xff\xfe\x00\x01",
        # Delimited correctly and malformed inside, which is the only shape
        # that reaches the XML parser at all.
        b"<x:xmpmeta><rdf:RDF><dc:title>no closing tag</rdf:RDF></x:xmpmeta>",
    ],
)
def test_a_packet_that_will_not_parse_is_remarked_rather_than_fatal(raw):
    fields, history, remarks = parse_xmp(raw)
    assert fields == [] and history == []
    if raw:
        assert remarks


def test_a_pdf_with_no_packet_at_all_yields_nothing_and_says_nothing():
    meta = meta_of(SPECIMENS / "pdf" / "libreoffice-writer-black-bars.pdf")
    assert all(entry.part == "/Info" for entry in meta.fields)
    assert not any("XMP" in remark for remark in meta.remarks)
