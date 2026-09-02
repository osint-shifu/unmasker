"""Metadata: what the file says about itself that the document never shows.

`filetrail` already reads these fields, and reads more containers than this
does. It answers a different question with them - *where did this file come
from* - and reports every field as an origin claim. What is added here is the
gap: a value in the metadata that the document does not show is something a
reader of the page cannot know, and that is this tool's subject.

Which means most metadata is **not** a finding. Every PDF has a Producer and
every .docx an Application; if those fired, the tool would exit non-zero on
every document ever written and the exit code would stop meaning anything.
They are remarks. A name, a client, a codename or a path is a finding.

The test that matters most here is
`test_a_version_in_an_application_field_is_not_read_as_an_address`. `CONTRIBUTING.md`
sets it out: `LibreOffice/24.2.7.2$Linux_X86_64` contains a dotted quad, and
pattern-matching alone reports an IP address. The field is called
`Application`. Context you already have beats a cleverer pattern.
"""

import zipfile

import pytest
from conftest import SPECIMENS
from pypdf import PdfReader

from unmasker.findings import Basis
from unmasker.metadata import Field, Metadata, read_ooxml, read_pdf
from unmasker.metadata.detectors import detect

PDF_LEAK = SPECIMENS / "pdf" / "libreoffice-writer-metadata-leak.pdf"
DOCX_LEAK = SPECIMENS / "docx" / "libreoffice-writer-metadata-leak.docx"

VISIBLE = "The board notes the position and will revert in due course."


def pdf_meta(path=PDF_LEAK) -> Metadata:
    return read_pdf(PdfReader(str(path)))


def docx_meta(path=DOCX_LEAK) -> Metadata:
    with zipfile.ZipFile(path) as archive:
        return read_ooxml(archive)


def reads(findings, detector=None):
    return sorted(f.machine_reads for f in findings if detector in (None, f.detector))


# --------------------------------------------------------------------------
# the name of a field is evidence
# --------------------------------------------------------------------------


def test_a_version_in_an_application_field_is_not_read_as_an_address():
    """The worked example from CONTRIBUTING.md, held to.

    `LibreOffice/24.2.7.2$Linux_X86_64` has a dotted quad in it. Nothing here
    may call it an address, a path, or a leak: the field is called
    `Application`, so it is a version, and it is a remark.
    """
    meta = docx_meta()
    application = meta.get("Application")
    assert application is not None
    assert "24.2.7.2" in application.value
    assert application.role == "tool"

    found = detect(meta, VISIBLE)
    assert not any("24.2.7.2" in f.machine_reads for f in found)
    everything = " ".join(f.summary for f in found)
    assert "address" not in everything.lower()


def test_the_same_field_name_means_different_things_in_different_containers():
    """A PDF's `/Creator` is the application that made the original document.
    An OOXML `dc:creator` is a person. One name, two meanings, and only the
    container tells them apart."""
    assert pdf_meta().get("Creator").role == "tool"
    assert docx_meta().get("creator").role == "content"


def test_tool_fields_are_never_findings():
    found = detect(pdf_meta(), VISIBLE)
    everything = " ".join(f.machine_reads for f in found)
    assert "LibreOffice 24.2" not in everything
    assert "Writer" not in everything


def test_every_field_is_kept_even_when_it_is_not_reported():
    """filetrail's rule: no fixed list anticipates which property an
    investigation will want. Nothing is dropped from the record; the roles only
    decide what becomes a finding."""
    names = {f.name for f in docx_meta().fields}
    assert {"creator", "Application", "TotalTime", "Client"} <= names


# --------------------------------------------------------------------------
# what is a finding
# --------------------------------------------------------------------------


def test_a_person_named_only_in_the_metadata_is_reported():
    found = detect(pdf_meta(), VISIBLE)
    assert "Marek Wysocki-Test" in reads(found)
    assert all(f.basis is Basis.SELF_REPORTED for f in found)


def test_a_title_and_a_codename_the_document_never_shows_are_reported():
    found = reads(detect(pdf_meta(), VISIBLE))
    assert "Board briefing - restricted" in found
    assert "Project Harrow" in found


def test_custom_properties_are_reported():
    found = reads(detect(docx_meta(), VISIBLE))
    assert "Acme Holdings BV" in found


def test_a_value_the_document_does_show_is_not_a_finding():
    """No gap, no finding. A title that is printed on the page is not hidden."""
    meta = Metadata(fields=(Field("Title", "Board briefing", "/Info", "content"),))
    assert detect(meta, "Board briefing\nand more text") == []
    assert len(detect(meta, "something else entirely")) == 1


def test_the_match_against_the_document_ignores_case():
    meta = Metadata(fields=(Field("Author", "Anna Testowa", "/Info", "content"),))
    assert detect(meta, "prepared by anna testowa") == []


def test_an_empty_value_is_not_a_finding():
    meta = Metadata(fields=(Field("Title", "   ", "/Info", "content"),))
    assert detect(meta, "text") == []


def test_a_very_short_value_is_not_matched_against_the_text_by_accident():
    """A two-character value would be inside almost any document by chance, and
    a finding suppressed by chance is worse than one never made."""
    meta = Metadata(fields=(Field("Category", "PL", "/Info", "content"),))
    assert len(detect(meta, "a document containing the letters PL somewhere")) == 1


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------


def test_a_path_is_its_own_finding():
    found = detect(docx_meta(), VISIBLE)
    paths = [f for f in found if f.detector == "metadata-path"]
    assert len(paths) == 1
    assert paths[0].machine_reads == "/home/mwysocki/Templates/acme-board-restricted.ott"


def test_a_path_is_not_also_reported_as_undisclosed_metadata():
    """Two names for one fact. The path finding says everything the other would."""
    found = detect(docx_meta(), VISIBLE)
    assert sum(1 for f in found if "mwysocki" in f.machine_reads) == 1


@pytest.mark.parametrize(
    "value",
    [
        "/home/someone/Documents/draft.docx",
        "C:\\Users\\someone\\Desktop\\draft.docx",
        "\\\\fileserver\\legal\\templates\\board.dotx",
    ],
)
def test_the_path_shapes_that_turn_up_in_real_documents(value):
    meta = Metadata(fields=(Field("Template", value, "docProps/app.xml", "content"),))
    (found,) = detect(meta, "unrelated text")
    assert found.detector == "metadata-path"


@pytest.mark.parametrize(
    "value",
    ["LibreOffice/24.2.7.2$Linux_X86_64", "Project Harrow", "1.4", "24.2.7.2"],
)
def test_things_that_are_not_paths(value):
    meta = Metadata(fields=(Field("Subject", value, "/Info", "content"),))
    assert not any(f.detector == "metadata-path" for f in detect(meta, "unrelated"))


# --------------------------------------------------------------------------
# dates
# --------------------------------------------------------------------------


def test_a_modification_earlier_than_the_creation_is_reported():
    meta = Metadata(
        fields=(
            Field("CreationDate", "2024-05-01T10:00:00Z", "/Info", "time"),
            Field("ModDate", "2024-01-02T09:00:00Z", "/Info", "time"),
        )
    )
    (found,) = [f for f in detect(meta, "text") if f.detector == "metadata-conflict"]
    assert found.basis is Basis.SELF_REPORTED
    assert "2024-01-02" in found.machine_reads


def test_dates_in_the_ordinary_order_are_not_reported():
    meta = Metadata(
        fields=(
            Field("CreationDate", "2024-01-02T09:00:00Z", "/Info", "time"),
            Field("ModDate", "2024-05-01T10:00:00Z", "/Info", "time"),
        )
    )
    assert not any(f.detector == "metadata-conflict" for f in detect(meta, "text"))


def test_pdf_dates_are_normalised_from_their_own_format():
    meta = pdf_meta()
    created = meta.get("CreationDate")
    assert created.value.startswith("20") and "T" in created.value


def test_an_unparseable_date_is_kept_as_written_rather_than_dropped():
    meta = Metadata(fields=(Field("CreationDate", "not a date", "/Info", "time"),))
    assert not any(f.detector == "metadata-conflict" for f in detect(meta, "text"))
    assert meta.get("CreationDate").value == "not a date"


class StubReader:
    """Enough of a pypdf reader for `read_pdf`. Some Info dictionaries in the
    wild hold values no producer should have written."""

    def __init__(self, metadata):
        self.metadata = metadata
        self.xmp_metadata = None


def test_a_date_the_reader_cannot_parse_is_kept_as_the_file_wrote_it():
    """Dropping it would be the tool deciding the file had said nothing. It
    said something; it just did not say it in the expected form."""
    meta = read_pdf(StubReader({"/CreationDate": "sometime last spring"}))
    assert meta.get("CreationDate").value == "sometime last spring"


def test_a_well_formed_pdf_date_is_normalised_by_the_reader():
    meta = read_pdf(StubReader({"/ModDate": "D:20240419164100+02'00'"}))
    assert meta.get("ModDate").value.startswith("2024-04-19T16:41")


def test_a_tool_field_that_looks_like_a_path_is_still_a_tool_field():
    """Some producers write a path into /Producer. It is still the thing that
    made the file, and reporting it as a leaked directory would be the same
    mistake as reading a version as an address."""
    meta = read_pdf(StubReader({"/Producer": "/usr/local/bin/some-converter"}))
    assert meta.get("Producer").role == "tool"
    assert detect(meta, "unrelated text") == []


def test_the_record_holds_no_empty_fields():
    """LibreOffice writes `<dc:description></dc:description>` and an empty
    `<Template>`. Keeping those would pad the record and the notes with fields
    that say nothing."""
    for meta in (docx_meta(), pdf_meta()):
        assert all(entry.value.strip() for entry in meta.fields)
    assert docx_meta().get("description") is None


# --------------------------------------------------------------------------
# the quiet specimens
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "specimen",
    [
        "libreoffice-writer-black-bars.pdf",
        "libreoffice-writer-properly-redacted.pdf",
        "flattened-to-image.pdf",
    ],
)
def test_the_bar_specimens_have_nothing_to_report_in_their_metadata(specimen):
    """They carry a producer and a date and nothing else. A tool that fired on
    those would fire on every document in the world."""
    meta = pdf_meta(SPECIMENS / "pdf" / specimen)
    assert detect(meta, "any text at all") == []


def test_the_chrome_specimen_reports_only_its_title():
    """Chrome writes the page title into /Title. It is not on the page, so it
    is a gap - a small one, correctly found."""
    meta = pdf_meta(SPECIMENS / "pdf" / "chrome-print-css-overlay.pdf")
    found = detect(meta, "unrelated document text")
    assert reads(found) == ["Synthetic disclosure"]


# --------------------------------------------------------------------------
# damage
# --------------------------------------------------------------------------


def test_a_zip_with_no_docprops_yields_an_empty_record():
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<x/>")
    buffer.seek(0)
    meta = read_ooxml(zipfile.ZipFile(buffer))
    assert meta.fields == ()
    assert detect(meta, "text") == []


def test_malformed_docprops_are_remarked_rather_than_fatal():
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("docProps/core.xml", "<not well formed")
        archive.writestr(
            "docProps/app.xml",
            '<Properties xmlns="http://schemas.openxmlformats.org/'
            'officeDocument/2006/extended-properties"><Company>Acme</Company></Properties>',
        )
    buffer.seek(0)
    meta = read_ooxml(zipfile.ZipFile(buffer))
    assert meta.get("Company").value == "Acme"
    assert any("core.xml" in r for r in meta.remarks)
