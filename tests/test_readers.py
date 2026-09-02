"""Turning a file into text, and being honest about how much text there was.

The rule these tests exist to enforce is the one `CONTRIBUTING.md` names: **"nothing
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
    """The distinction that CONTRIBUTING.md says a reader must never have to guess."""
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
    body = "\n".join(u.text for u in read(DOCX / "libreoffice-writer-hidden-characters.docx").units)
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


# --------------------------------------------------------------------------
# the painted layer
# --------------------------------------------------------------------------


def test_pdf_extraction_carries_what_was_drawn_on_each_page():
    """Task 4 needs the shapes and the text together. The reader is the layer
    that opens the file, so it is where both come from."""
    got = read(SPECIMENS / "libreoffice-writer-black-bars.pdf")
    assert len(got.drawn) == 1
    fills = [s for s in got.drawn[0].shapes if s.kind == "fill"]
    assert len(fills) == 4
    assert all(s.colour.rgb == (0, 0, 0) for s in fills)


def test_a_page_with_no_text_layer_says_what_is_painted_on_it_instead():
    """'Nothing to search' is more useful when it also says what is there.
    A page with an image on it and no text is the OCR case, and saying so is
    the difference between a dead end and a next step."""
    got = read(SPECIMENS / "flattened-to-image.pdf")
    note = " ".join(got.remarks)
    assert "no text layer" in note
    assert "image" in note
    assert "--ocr" in note, "the note has to name the way to read it"


def test_the_note_only_names_a_flag_that_would_work(monkeypatch):
    """CONTRIBUTING.md: every command the tool prints must run in the shell that
    printed it. filetrail printed `filetrail --help` at somebody who had not
    installed it, and the screen was disproved by the first thing they tried."""
    import unmasker.pdf.rendered as rendered

    monkeypatch.setattr(rendered.shutil, "which", lambda name: None)
    note = " ".join(read(SPECIMENS / "flattened-to-image.pdf").remarks)
    assert "neither is here" in note
    assert "gs" in note and "tesseract" in note


def test_a_plain_file_has_nothing_drawn(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("hello", encoding="utf-8")
    assert read(f).drawn == ()


# --------------------------------------------------------------------------
# presentations, which this tool does not read
#
# The dangerous case is not the one it refuses. An .odp is a zip with a
# content.xml in it, which is also the description of an .odt, so it used to
# reach the reader for text documents - and that reader has no concept of a
# slide nobody sees. It read a hidden slide's text and a speaker note as
# ordinary visible prose and then reported the deck clean, which is the same
# defect the spreadsheet reader was written to remove, one container over.
#
# Refusing is the honest answer until there is a reader, and until there is a
# specimen a real producer wrote. `libreoffice-impress` is not installed on
# this machine, so nothing here can produce one.
# --------------------------------------------------------------------------

PRESENTATION = "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"


def _odp(path):
    import zipfile

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.presentation")
        z.writestr(
            "content.xml",
            '<office:document-content'
            ' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
            ' xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"'
            f' xmlns:presentation="{PRESENTATION}"'
            ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            "<office:body><office:presentation>"
            '<draw:page draw:name="shown"><text:p>Quarterly review</text:p></draw:page>'
            '<draw:page draw:name="cut"><text:p>SLIDE THAT IS HIDDEN</text:p>'
            "<presentation:notes><text:p>Do not say the headcount out loud.</text:p>"
            "</presentation:notes></draw:page>"
            "</office:presentation></office:body></office:document-content>",
        )
    return path


def test_an_opendocument_presentation_is_refused_rather_than_read_as_prose(tmp_path):
    with pytest.raises(UnreadableFile) as refusal:
        read(_odp(tmp_path / "deck.odp"))
    assert "presentation" in str(refusal.value)


def test_the_refusal_says_what_would_have_to_change(tmp_path):
    """A message that only says no teaches a reader nothing. This one names
    the thing that is missing, so the answer to `why not` is on the screen."""
    with pytest.raises(UnreadableFile) as refusal:
        read(_odp(tmp_path / "deck.odp"))
    assert "slide" in str(refusal.value).lower()


def test_a_hidden_slide_is_never_reported_as_visible_text(tmp_path):
    """The regression. Reading a deck as a text document does not merely miss
    a finding: it hands concealed content to the detectors as though a person
    could see it, and then reports the file clean."""
    from unmasker.cli import main

    assert main([str(_odp(tmp_path / "deck.odp"))]) == 2


def test_a_powerpoint_file_is_refused_the_same_way(tmp_path):
    """Both families, one answer. The two disagreeing about whether a deck can
    be read would be the tool contradicting itself."""
    import zipfile

    f = tmp_path / "deck.pptx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", "<presentation/>")
    with pytest.raises(UnreadableFile) as refusal:
        read(f)
    assert "presentation" in str(refusal.value)
