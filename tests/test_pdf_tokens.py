"""Reading a content stream into tokens.

A content stream is a postfix language with six literal types and a lot of ways
to get the lexing wrong. Every case below is one a real file will present, and
several of them desynchronise a naive tokenizer so quietly that the operators
after them are read as garbage - which is the worst failure mode available
here, because the stream keeps parsing and starts lying.

The inline-image cases matter most. `BI ... ID <binary> EI` embeds arbitrary
bytes in the middle of the language, and those bytes can contain `EI`. Get that
wrong and every operator after the first inline image is nonsense.
"""

import pytest

from unmasker.pdf.tokens import InlineImage, Name, Operator, tokenize


def toks(data: str | bytes):
    return list(tokenize(data.encode("latin-1") if isinstance(data, str) else data))


# --------------------------------------------------------------------------
# numbers
# --------------------------------------------------------------------------


def test_integers_and_reals():
    assert toks("0 1 -2 3.5 -4.25") == [0.0, 1.0, -2.0, 3.5, -4.25]


def test_the_number_forms_the_specification_allows_but_nobody_expects():
    """`4.` and `.5` and `-.002` are all legal, and producers emit them."""
    assert toks("4. .5 -.002 +7") == [4.0, 0.5, -0.002, 7.0]


def test_a_number_ending_the_stream_is_not_lost():
    assert toks("1 2 3") == [1.0, 2.0, 3.0]


# --------------------------------------------------------------------------
# names
# --------------------------------------------------------------------------


def test_names():
    assert toks("/F1 /Artifact") == [Name("F1"), Name("Artifact")]


def test_a_name_with_a_hash_escape():
    """`/A#20B` is the name `A B`. Producers use this for spaces in names."""
    assert toks("/A#20B") == [Name("A B")]


def test_a_name_is_ended_by_a_delimiter_not_only_by_space():
    assert toks("/F1(x)") == [Name("F1"), b"x"]


# --------------------------------------------------------------------------
# strings
# --------------------------------------------------------------------------


def test_a_plain_string():
    assert toks("(hello)") == [b"hello"]


def test_balanced_parens_nest_inside_a_string():
    """Unescaped parens are legal if balanced, and this is where naive
    tokenizers stop early and desynchronise the rest of the stream."""
    assert toks("(a (nested) b)") == [b"a (nested) b"]


def test_escaped_parens_do_not_open_or_close():
    assert toks(r"(a \( b \) c)") == [b"a ( b ) c"]


def test_backslash_escapes():
    assert toks(r"(tab\there)") == [b"tab\there"]
    assert toks(r"(back\\slash)") == [b"back\\slash"]


def test_octal_escapes():
    assert toks(r"(\101\102\103)") == [b"ABC"]


def test_a_backslash_before_a_newline_is_a_line_continuation():
    assert toks("(one\\\ntwo)") == [b"onetwo"]


def test_a_string_may_hold_raw_bytes_including_a_newline():
    assert toks("(a\nb)") == [b"a\nb"]


# --------------------------------------------------------------------------
# hex strings, arrays, dictionaries
# --------------------------------------------------------------------------


def test_hex_string():
    assert toks("<48656C6C6F>") == [b"Hello"]


def test_an_odd_length_hex_string_is_padded_with_a_zero():
    assert toks("<4>") == [b"\x40"]


def test_hex_string_ignores_whitespace():
    assert toks("<48 65 6C>") == [b"Hel"]


def test_array():
    assert toks("[1 2 (a)]") == [[1.0, 2.0, b"a"]]


def test_the_array_form_that_TJ_takes():
    assert toks("[<0102> -250 <0304>] TJ") == [
        [b"\x01\x02", -250.0, b"\x03\x04"],
        Operator("TJ"),
    ]


def test_dictionary():
    assert toks("<</Type /Foo /N 3>>") == [{"Type": Name("Foo"), "N": 3.0}]


def test_a_dictionary_is_not_read_as_a_hex_string():
    """`<<` opens a dictionary; `<` opens a hex string. One character apart."""
    assert toks("<</A 1>> <41>") == [{"A": 1.0}, b"A"]


# --------------------------------------------------------------------------
# operators, comments, keywords
# --------------------------------------------------------------------------


def test_operators():
    assert toks("q 1 0 0 1 0 0 cm Q") == [
        Operator("q"),
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        Operator("cm"),
        Operator("Q"),
    ]


def test_star_and_quote_operators_are_single_tokens():
    assert toks("f* W* B* T* ' \"") == [
        Operator("f*"),
        Operator("W*"),
        Operator("B*"),
        Operator("T*"),
        Operator("'"),
        Operator('"'),
    ]


def test_comments_are_skipped():
    assert toks("1 % this is ignored\n2") == [1.0, 2.0]


def test_a_percent_inside_a_string_is_not_a_comment():
    assert toks("(100% sure) 1") == [b"100% sure", 1.0]


def test_the_boolean_and_null_keywords():
    assert toks("true false null") == [True, False, None]


# --------------------------------------------------------------------------
# inline images
# --------------------------------------------------------------------------


def test_an_inline_image_is_one_token():
    stream = b"BI /W 2 /H 2 /BPC 8 /CS /G ID \x00\x01\x02\x03 EI Q"
    got = toks(stream)
    assert isinstance(got[0], InlineImage)
    assert got[0].params["W"] == 2.0
    assert got[0].data == b"\x00\x01\x02\x03"
    assert got[1] == Operator("Q")


def test_an_inline_image_whose_data_contains_the_bytes_EI():
    """The terminator has to be delimited, or the image ends early and every
    operator after it is read out of the middle of a picture."""
    payload = b"\x00EI\x01\x02\x03\x04\x05\x06\x07\x08"
    stream = b"BI /W 4 /H 1 /BPC 8 /CS /G ID " + payload + b" EI\nQ"
    got = toks(stream)
    assert isinstance(got[0], InlineImage)
    assert got[0].data == payload
    assert got[1] == Operator("Q")


def test_an_inline_image_whose_data_holds_EI_with_no_space_before_it():
    """The other half of the delimiter rule. In the case above, the byte before
    the false `EI` was NUL - which PDF counts as whitespace - so only the
    trailing check was doing any work. Here the leading byte is a letter, and
    only the leading check can save the stream."""
    payload = b"\x41EI\x20\x01\x02\x03\x04"
    stream = b"BI /W 4 /H 1 /BPC 8 /CS /G ID " + payload + b" EI\nQ"
    got = toks(stream)
    assert isinstance(got[0], InlineImage)
    assert got[0].data == payload
    assert got[1] == Operator("Q")


def test_an_inline_image_with_an_explicit_length_is_taken_at_its_word():
    payload = b" EI junk \x00\x01"
    stream = b"BI /W 1 /H 1 /L " + str(len(payload)).encode() + b" ID " + payload + b" EI Q"
    got = toks(stream)
    assert got[0].data == payload
    assert got[1] == Operator("Q")


# --------------------------------------------------------------------------
# damage
# --------------------------------------------------------------------------


def test_an_unterminated_string_does_not_hang_or_raise():
    assert toks("(never closed") == [b"never closed"]


def test_an_unterminated_dictionary_does_not_hang_or_raise():
    assert toks("<</A 1") == [{"A": 1.0}]


def test_an_unterminated_array_does_not_hang_or_raise():
    assert toks("[1 2") == [[1.0, 2.0]]


def test_an_empty_stream_yields_nothing():
    assert toks("") == []


@pytest.mark.parametrize("junk", [b"\xff\xfe\x00", b")))", b">>>>", b"\x00" * 32])
def test_garbage_is_survived(junk):
    """A forensic tool is pointed at damaged files on purpose."""
    tokenize(junk)  # must not raise
    assert list(tokenize(junk + b" 1 2 re f"))[-1] == Operator("f")
