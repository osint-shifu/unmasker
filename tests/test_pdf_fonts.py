"""Font metrics: how wide a glyph is, and which character it is.

This is a table lookup, not a font decoder. `HANDOFF.md` forbids the second and
it is right to: the specimens' text is written `<010203040506>` in a subset font
with a custom encoding, and resolving that from the glyph program would be
months. pypdf already resolves it, and this module asks pypdf for the answer.

What unmasker does own is the arithmetic pypdf does not expose: a glyph's
*width*, which is what turns "the text starts here" into "the text occupies
this rectangle", and without which a bar covering half a line cannot be told
from one covering all of it.

Both specimens are needed because they use the two different width tables.
LibreOffice writes simple TrueType fonts with `/FirstChar` and `/Widths`, one
byte per code. Chrome writes Type0 fonts with `/W`, `/DW` and Identity-H, two
bytes per code. A module tested against only one of them handles half the PDFs
in the world.
"""

import pytest
from conftest import Stub, font_of

from unmasker.pdf.fonts import DEFAULT_ASCENT, DEFAULT_DESCENT, FontMetrics, load_font

# --------------------------------------------------------------------------
# simple fonts: /FirstChar and /Widths
# --------------------------------------------------------------------------


def test_a_simple_truetype_font_reads_its_widths_array():
    font = load_font(font_of("libreoffice-writer-black-bars.pdf", "/F2"))
    assert font.width_source == "Widths"
    assert font.bytes_per_code == 1
    # /FirstChar is 0 and /Widths starts [0, 610, 500, 443, 250, ...]
    assert font.advance(1) == pytest.approx(0.610)
    assert font.advance(3) == pytest.approx(0.443)


def test_a_simple_font_takes_one_byte_per_code():
    font = load_font(font_of("libreoffice-writer-black-bars.pdf", "/F2"))
    assert font.codes(b"\x01\x02\x03") == [1, 2, 3]


def test_a_simple_font_decodes_its_codes_through_pypdf():
    """`\\x01\\x02\\x03` is `The` in this subset. Nothing here worked that out."""
    font = load_font(font_of("libreoffice-writer-black-bars.pdf", "/F2"))
    assert "".join(font.char(c) for c in (1, 2, 3)) == "The"


# --------------------------------------------------------------------------
# Type0 fonts: /W, /DW and two-byte codes
# --------------------------------------------------------------------------


def test_a_type0_font_reads_its_W_array():
    font = load_font(font_of("chrome-print-css-overlay.pdf", "/F4"))
    assert font.width_source == "W"
    assert font.bytes_per_code == 2
    assert font.advance(0) == pytest.approx(0.77783, abs=1e-4)
    assert font.advance(16) == pytest.approx(0.33300, abs=1e-4)
    assert font.advance(36) == pytest.approx(0.72216, abs=1e-4)  # a range entry


def test_identity_h_takes_two_bytes_per_code():
    font = load_font(font_of("chrome-print-css-overlay.pdf", "/F4"))
    assert font.codes(b"\x00\x24\x00\x03") == [0x24, 0x03]


def test_a_type0_font_decodes_its_cids_through_pypdf():
    font = load_font(font_of("chrome-print-css-overlay.pdf", "/F4"))
    assert font.char(0x24) == "A"
    assert font.char(0x03) == " "


def test_the_W_range_form_c_first_c_last_w():
    """`0 93 600.09766` gives every code from 0 to 93 the same width. This is
    the form the monospaced font in the Chrome specimen uses."""
    font = load_font(font_of("chrome-print-css-overlay.pdf", "/F6"))
    assert font.advance(0) == pytest.approx(0.60009, abs=1e-4)
    assert font.advance(93) == pytest.approx(0.60009, abs=1e-4)


def test_a_code_outside_W_falls_back_to_DW():
    font = Stub(
        Subtype="/Type0",
        Encoding="/Identity-H",
        DescendantFonts=[Stub(Subtype="/CIDFontType2", DW=333, W=[0, [500]])],
    )
    metrics = load_font(font)
    assert metrics.advance(0) == pytest.approx(0.5)
    assert metrics.advance(9999) == pytest.approx(0.333)


def test_both_W_forms_in_one_array():
    font = Stub(
        Subtype="/Type0",
        Encoding="/Identity-H",
        DescendantFonts=[Stub(Subtype="/CIDFontType2", DW=1000, W=[1, [100, 200], 5, 7, 300])],
    )
    m = load_font(font)
    assert m.advance(1) == pytest.approx(0.1)
    assert m.advance(2) == pytest.approx(0.2)
    assert m.advance(5) == pytest.approx(0.3)
    assert m.advance(7) == pytest.approx(0.3)
    assert m.advance(3) == pytest.approx(1.0)  # gap, so /DW


# --------------------------------------------------------------------------
# ascent and descent
# --------------------------------------------------------------------------


def test_ascent_and_descent_come_from_the_font_descriptor():
    font = load_font(font_of("libreoffice-writer-black-bars.pdf", "/F2"))
    assert font.ascent == pytest.approx(0.891)
    assert font.descent == pytest.approx(-0.216)


def test_a_type0_descriptor_is_found_on_the_descendant():
    font = load_font(font_of("chrome-print-css-overlay.pdf", "/F4"))
    assert font.ascent == pytest.approx(0.891, abs=1e-3)
    assert font.descent == pytest.approx(-0.216, abs=1e-3)


# --------------------------------------------------------------------------
# what happens when the file does not say
# --------------------------------------------------------------------------


def test_a_font_with_no_widths_says_so_rather_than_pretending():
    """A guessed width is a guessed rectangle, and a guessed rectangle would
    let the tool claim a bar covers text it may not touch."""
    metrics = load_font(Stub(Subtype="/TrueType"))
    assert metrics.width_source == "none"
    assert metrics.advance(65) == pytest.approx(metrics.default_width)


def test_a_font_with_no_descriptor_uses_stated_defaults():
    metrics = load_font(Stub(Subtype="/TrueType"))
    assert metrics.ascent == DEFAULT_ASCENT
    assert metrics.descent == DEFAULT_DESCENT


def test_an_undecodable_code_gives_an_empty_string_not_a_wrong_character():
    metrics = load_font(Stub(Subtype="/TrueType"))
    assert metrics.char(65) == ""
    assert metrics.text_source == "none"


def test_a_missing_font_still_produces_usable_metrics():
    """A `Tf` naming a font that is not in the resources must not stop the page
    from being read; it must produce a run whose extent is admitted to be an
    estimate."""
    metrics = load_font(None)
    assert isinstance(metrics, FontMetrics)
    assert metrics.width_source == "none"
    assert metrics.codes(b"AB") == [65, 66]


def test_an_odd_trailing_byte_in_a_two_byte_encoding_is_not_dropped_silently():
    font = Stub(Subtype="/Type0", Encoding="/Identity-H", DescendantFonts=[Stub(DW=500)])
    m = load_font(font)
    assert m.codes(b"\x00\x41\x00") == [0x41, 0x00]
