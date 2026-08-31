"""Turning a file into text, and being honest about how much text there was.

The rule these tests exist to enforce is the one `CLAUDE.md` names: **"nothing
found" has two meanings.** It can mean *searched, and it is not there*. It can
mean *there was nothing to search*. A reader who confuses the two has drawn a
conclusion the tool never supported, so the extraction has to carry that
difference out of the reader rather than let the report guess at it.

`tests/specimens/pdf/flattened-to-image.pdf` is the case in point: four black
bars, no fonts, no text objects. The tool must not say "no hidden text found"
about it.
"""

from pathlib import Path

import pytest

from unmasker.readers import UnreadableFile, read

SPECIMENS = Path(__file__).parent / "specimens" / "pdf"
DOCX = Path(__file__).parent / "specimens" / "docx"


# --------------------------------------------------------------------------
# plain text
# --------------------------------------------------------------------------


def test_plain_text_is_one_unit_with_no_page(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("# Heading\n\nBody text.\n", encoding="utf-8")
    got = read(f)
    assert got.kind == "plain"
    assert len(got.units) == 1
    assert got.units[0].page is None
    assert "Body text." in got.units[0].text
    assert got.has_text


def test_an_empty_file_has_nothing_to_search(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    got = read(f)
    assert not got.has_text
    assert got.remarks, "an empty file must say why there is nothing to search"


def test_a_file_that_is_not_text_is_refused_rather_than_guessed_at(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(bytes(range(256)) * 8)
    with pytest.raises(UnreadableFile):
        read(f)


def test_null_bytes_are_refused_even_though_they_decode_cleanly(tmp_path):
    """b"a\x00b" is valid UTF-8. It is still not a text file, and reporting
    findings out of whatever survives the decode would be reporting noise."""
    f = tmp_path / "sneaky.txt"
    f.write_bytes(b"header\x00\x00payload\x00text")
    with pytest.raises(UnreadableFile):
        read(f)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(UnreadableFile):
        read(tmp_path / "does-not-exist.txt")


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def test_pdf_units_carry_page_numbers():
    got = read(SPECIMENS / "libreoffice-writer-black-bars.pdf")
    assert got.kind == "pdf"
    assert [u.page for u in got.units] == [1]
    assert got.has_text


def test_pdf_text_includes_what_is_under_the_bars():
    """The specimen's whole point: the covered values are still readable."""
    got = read(SPECIMENS / "libreoffice-writer-black-bars.pdf")
    body = "\n".join(u.text for u in got.units)
    assert "w.testowa@example.org" in body
    assert "+48 601 000 000" in body


def test_a_page_with_no_text_layer_says_so_and_does_not_pretend_it_searched():
    """The distinction that CLAUDE.md says a reader must never have to guess."""
    got = read(SPECIMENS / "flattened-to-image.pdf")
    assert got.kind == "pdf"
    assert not got.has_text
    assert got.remarks
    assert any("no text layer" in r for r in got.remarks)


def test_a_properly_redacted_pdf_still_has_text_to_search():
    """Contrast with the flattened one: there *is* a text layer here, and the
    honest report is 'searched, and the values are not in it'."""
    got = read(SPECIMENS / "libreoffice-writer-properly-redacted.pdf")
    assert got.has_text
    assert not any("no text layer" in r for r in got.remarks)
    body = "\n".join(u.text for u in got.units)
    assert "w.testowa@example.org" not in body


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------


def test_docx_body_text_is_read():
    got = read(DOCX / "libreoffice-writer-hidden-characters.docx")
    assert got.kind == "docx"
    assert got.has_text
    body = "\n".join(u.text for u in got.units)
    assert "VENDOR ONBOARDING NOTE" in body
    assert "SYN-2024-0417" in body


def test_the_docx_specimen_still_carries_its_hidden_characters():
    """If a LibreOffice upgrade normalises these away, the specimen quietly
    stops being a specimen. This is the test that would notice."""
    body = "\n".join(
        u.text for u in read(DOCX / "libreoffice-writer-hidden-characters.docx").units
    )
    assert "\u200b" in body, "zero-width space did not survive the conversion"
    assert "\u202e" in body, "right-to-left override did not survive"
    assert any(0xE0000 <= ord(c) <= 0xE007F for c in body), "tag characters did not survive"
    assert "\u0430" in body, "Cyrillic homoglyph did not survive"


def test_a_zip_that_is_not_a_word_document_is_refused(tmp_path):
    import zipfile

    f = tmp_path / "not-word.docx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("hello.txt", "not a document")
    with pytest.raises(UnreadableFile):
        read(f)
