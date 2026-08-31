"""Tracked changes and comments: what Word agreed not to show.

A tracked deletion removes nothing. The struck-out run stays in the file as
`w:delText`, beside the name of whoever deleted it and the minute they did, and
a reader whose review pane shows the final text never sees any of it. That is
this tool's gap arriving through a mechanism with no geometry in it at all -
just a part of the file the application has agreed not to display.

The distinction that shapes these tests: **a deletion is hidden and an
insertion is not.** Inserted text is in the final document, in plain sight.
What it hides is who put it there and when, and that is one fact about the
file rather than one fact per insertion - so it is reported once, as the file's
own account of itself, and never as a wall of findings.
"""

import zipfile

import pytest
from conftest import SPECIMENS

from unmasker.findings import Basis
from unmasker.ooxml.detectors import detect
from unmasker.ooxml.revisions import read_revisions

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SPECIMEN = SPECIMENS / "docx" / "libreoffice-writer-tracked-changes.docx"


def record_of(path):
    with zipfile.ZipFile(path) as archive:
        return read_revisions(archive)


def synthetic(document: str, extra: dict[str, str] | None = None):
    """A minimal .docx in memory, for the edge cases no producer here makes."""
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document xmlns:w="{W}">'
            f"<w:body>{document}</w:body></w:document>",
        )
        for name, body in (extra or {}).items():
            archive.writestr(name, body)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


# --------------------------------------------------------------------------
# the specimen
# --------------------------------------------------------------------------


def test_both_deletions_are_found_with_their_text():
    record = record_of(SPECIMEN)
    deleted = [r for r in record.revisions if r.kind == "deletion"]
    assert len(deleted) == 2
    assert "250,000 EUR" in {r.text for r in deleted}
    assert any("1.4 million EUR" in r.text for r in deleted)


def test_xml_entities_in_deleted_text_are_resolved():
    """The deleted sentence contains an apostrophe, which OOXML writes as
    `&apos;`. Reporting the entity would be reporting the encoding."""
    record = record_of(SPECIMEN)
    sentence = next(r.text for r in record.revisions if "expert" in r.text)
    assert "'" in sentence
    assert "&apos;" not in sentence


def test_each_deletion_carries_its_author_and_date():
    record = record_of(SPECIMEN)
    by_text = {r.text: r for r in record.revisions if r.kind == "deletion"}
    figure = by_text["250,000 EUR"]
    assert figure.author == "Anna Testowa"
    assert figure.date.startswith("2024-04-17T10:22")
    sentence = next(r for t, r in by_text.items() if "expert" in t)
    assert sentence.author == "Piotr Przyklad"


def test_the_insertion_is_recorded_but_is_not_hidden_text():
    record = record_of(SPECIMEN)
    inserted = [r for r in record.revisions if r.kind == "insertion"]
    assert len(inserted) == 1
    assert "90,000 EUR" in inserted[0].text


def test_the_comment_is_found_with_its_author():
    record = record_of(SPECIMEN)
    (comment,) = record.comments
    assert "Do not send this version" in comment.text
    assert comment.author == "Anna Testowa"
    assert comment.date.startswith("2024-04-19")


def test_the_authors_are_gathered_without_repeats():
    record = record_of(SPECIMEN)
    assert sorted(record.authors) == ["Anna Testowa", "Piotr Przyklad"]


# --------------------------------------------------------------------------
# the findings
# --------------------------------------------------------------------------


def test_a_deletion_becomes_a_finding_showing_what_was_removed():
    found = [f for f in detect(record_of(SPECIMEN)) if f.detector == "deleted-text"]
    assert len(found) == 2
    figure = next(f for f in found if "250,000" in f.machine_reads)
    assert figure.basis is Basis.DIRECT
    assert figure.human_sees == ""
    assert "Anna Testowa" in figure.summary
    assert "2024-04-17" in figure.summary


def test_a_comment_becomes_a_finding():
    (found,) = [f for f in detect(record_of(SPECIMEN)) if f.detector == "comment"]
    assert "Do not send this version" in found.machine_reads
    assert "Anna Testowa" in found.summary


def test_the_revision_history_is_one_finding_not_one_per_change():
    """Who edited a file and when is one fact about the file. A document with
    two hundred insertions must not produce two hundred findings."""
    found = [f for f in detect(record_of(SPECIMEN)) if f.detector == "revision-history"]
    assert len(found) == 1
    assert found[0].basis is Basis.SELF_REPORTED
    assert "Anna Testowa" in found[0].machine_reads
    assert "Piotr Przyklad" in found[0].machine_reads


def test_the_revision_history_names_the_span_of_dates():
    (found,) = [f for f in detect(record_of(SPECIMEN)) if f.detector == "revision-history"]
    assert "2024-04-17" in found.summary
    assert "2024-04-19" in found.summary


def test_an_insertion_alone_produces_no_hidden_text_finding():
    archive = synthetic(
        '<w:p><w:ins w:id="1" w:author="A" w:date="2024-01-01T00:00:00Z">'
        "<w:r><w:t>added words</w:t></w:r></w:ins></w:p>"
    )
    found = detect(read_revisions(archive))
    assert [f.detector for f in found] == ["revision-history"]


# --------------------------------------------------------------------------
# the shapes a real file takes
# --------------------------------------------------------------------------


def test_a_document_with_no_revisions_yields_nothing():
    archive = synthetic("<w:p><w:r><w:t>Plain text.</w:t></w:r></w:p>")
    record = read_revisions(archive)
    assert record.revisions == ()
    assert record.comments == ()
    assert detect(record) == []


def test_a_deleted_paragraph_mark_is_counted_but_has_no_text_to_show():
    """`w:del` inside `w:rPr` inside `w:pPr` deletes the paragraph mark, which
    merges two paragraphs. There is no `w:delText` and nothing to quote."""
    archive = synthetic(
        '<w:p><w:pPr><w:rPr><w:del w:id="1" w:author="A" '
        'w:date="2024-01-01T00:00:00Z"/></w:rPr></w:pPr>'
        "<w:r><w:t>text</w:t></w:r></w:p>"
    )
    record = read_revisions(archive)
    assert len(record.revisions) == 1
    assert record.revisions[0].text == ""
    assert [f.detector for f in detect(record)] == ["revision-history"]


def test_a_deletion_nested_inside_another_is_not_counted_twice():
    archive = synthetic(
        '<w:p><w:del w:id="1" w:author="A" w:date="2024-01-01T00:00:00Z">'
        "<w:r><w:delText>outer </w:delText></w:r>"
        '<w:del w:id="2" w:author="B" w:date="2024-01-02T00:00:00Z">'
        "<w:r><w:delText>inner</w:delText></w:r></w:del></w:del></w:p>"
    )
    record = read_revisions(archive)
    assert len(record.revisions) == 1
    assert record.revisions[0].text == "outer inner"


def test_moved_text_is_treated_as_a_deletion_at_the_place_it_left():
    archive = synthetic(
        '<w:p><w:moveFrom w:id="1" w:author="A" w:date="2024-01-01T00:00:00Z">'
        "<w:r><w:delText>this moved away</w:delText></w:r></w:moveFrom></w:p>"
    )
    record = read_revisions(archive)
    assert record.revisions[0].kind == "move-from"
    found = [f for f in detect(record) if f.detector == "deleted-text"]
    assert found[0].machine_reads == "this moved away"


def test_revisions_in_a_header_are_found_too():
    archive = synthetic(
        "<w:p><w:r><w:t>body</w:t></w:r></w:p>",
        {
            "word/header1.xml": (
                f'<?xml version="1.0"?><w:hdr xmlns:w="{W}"><w:p>'
                f'<w:del w:id="1" w:author="A" w:date="2024-01-01T00:00:00Z">'
                f"<w:r><w:delText>struck from the header</w:delText></w:r>"
                f"</w:del></w:p></w:hdr>"
            )
        },
    )
    record = read_revisions(archive)
    assert record.revisions[0].text == "struck from the header"
    assert record.revisions[0].part.endswith("header1.xml")


def test_formatting_changes_are_remarked_rather_than_reported_as_text():
    """`w:rPrChange` records that someone changed a font. It carries an author
    but no hidden text, and reporting it as a finding would be noise."""
    archive = synthetic(
        '<w:p><w:r><w:rPr><w:rPrChange w:id="1" w:author="A" '
        'w:date="2024-01-01T00:00:00Z"><w:rPr/></w:rPrChange></w:rPr>'
        "<w:t>text</w:t></w:r></w:p>"
    )
    record = read_revisions(archive)
    assert record.revisions == ()
    assert any("formatting" in r for r in record.remarks)


def test_malformed_xml_in_one_part_does_not_lose_the_others():
    archive = synthetic(
        '<w:p><w:del w:id="1" w:author="A" w:date="2024-01-01T00:00:00Z">'
        "<w:r><w:delText>survives</w:delText></w:r></w:del></w:p>",
        {"word/header1.xml": "<not well formed"},
    )
    record = read_revisions(archive)
    assert record.revisions[0].text == "survives"
    assert any("header1" in r for r in record.remarks)


@pytest.mark.parametrize("missing", ["author", "date"])
def test_a_revision_with_no_author_or_date_is_still_reported(missing):
    attrs = {"author": 'w:author="A"', "date": 'w:date="2024-01-01T00:00:00Z"'}
    attrs.pop(missing)
    archive = synthetic(
        f'<w:p><w:del w:id="1" {" ".join(attrs.values())}>'
        f"<w:r><w:delText>still hidden</w:delText></w:r></w:del></w:p>"
    )
    found = [f for f in detect(read_revisions(archive)) if f.detector == "deleted-text"]
    assert found[0].machine_reads == "still hidden"
    assert "does not state" in found[0].summary
