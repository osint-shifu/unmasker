"""The compound file: a filesystem inside a file.

`.doc`, `.xls` and `.ppt` are not zips and not XML. Each is a FAT filesystem in
one file - sectors, an allocation table, a directory tree - with a second,
smaller filesystem nested inside it for streams below 4096 bytes. Nothing in
the standard library reads one, and this project has one runtime dependency
which is not going to become two.

Every number asserted here was read out of the specimen before the reader
existed. That order matters more than usual for a binary format: the
specification permits a great deal that no producer writes, and the one thing
it does not warn about is that in a real Word file **every stream worth having
is under the 4096-byte cutoff**, so a reader that leaves the mini stream for
later reads nothing at all.
"""

from pathlib import Path

import pytest

from unmasker.ole2 import CompoundFile, NotACompoundFile

SPECIMEN = Path(__file__).parent / "specimens" / "doc" / "libreoffice-writer-word97.doc"

#: A workbook, whose text this tool still does not read. The claims below
#: about a file that was *not* searched need a file that was not searched, and
#: a .doc stopped being one when `unmasker.word` landed.
WORKBOOK = Path(__file__).parent / "specimens" / "xls" / "libreoffice-calc-excel97.xls"


@pytest.fixture
def compound():
    return CompoundFile(SPECIMEN.read_bytes())


def test_a_file_that_is_not_one_is_refused_rather_than_guessed_at():
    with pytest.raises(NotACompoundFile):
        CompoundFile(b"PK\x03\x04not a compound file at all")


def test_the_directory_lists_every_stream(compound):
    assert set(compound.names) == {
        "\x01CompObj",
        "\x01Ole",
        "1Table",
        "\x05SummaryInformation",
        "WordDocument",
        "\x05DocumentSummaryInformation",
    }


def test_the_root_entry_is_not_offered_as_a_stream(compound):
    """It is the mini stream's container, not a stream anybody wants."""
    assert "Root Entry" not in compound.names


def test_a_stream_comes_back_at_the_length_the_directory_claims(compound):
    assert len(compound.read("\x05SummaryInformation")) == 368
    assert len(compound.read("WordDocument")) == 3631


def test_the_mini_stream_is_read_and_not_deferred(compound):
    """Every stream in this file is under the cutoff. A reader that handled
    only full sectors would return nothing here and pass a suite full of
    fixtures built the way the specification reads."""
    assert all(len(compound.read(name)) < 4096 for name in compound.names)
    assert compound.read("\x05SummaryInformation").startswith(b"\xfe\xff")


def test_asking_for_a_stream_that_is_not_there_says_so(compound):
    with pytest.raises(KeyError):
        compound.read("Workbook")


# The property sets. A compound file's metadata is not XML and not key=value:
# it is a serialised property set, numbered rather than named, with its own
# code page and its own idea of a string.

from unmasker.ole2.properties import read_properties  # noqa: E402


def test_the_summary_gives_back_what_the_producer_was_told(compound):
    """A round trip. Every value here was set in the source the specimen was
    built from, so this checks the reader against the producer rather than
    against the specification's account of the producer."""
    found = read_properties(compound.read("\x05SummaryInformation"))
    assert found["Title"] == "Panel copy - do not circulate"
    assert found["Subject"] == "Tender evaluation"
    assert found["Author"] == "Halina Probna-Test"
    assert found["Keywords"] == "reserve; internal"
    assert found["Last Saved By"] == "Marek Zapasowy-Przyklad"
    assert found["Revision Number"] == "23"


def test_the_second_property_set_is_read_as_well(compound):
    found = read_properties(compound.read("\x05DocumentSummaryInformation"))
    assert found["Company"] == "Osint Shifu sp. z o.o."


def test_a_string_is_decoded_with_the_code_page_the_file_declares(compound):
    """This file declares 65001. Assuming the specification's usual CP1252
    would return the right answer for ASCII and mangle every name with a
    diacritic in it, which is most names this tool will ever see."""
    found = read_properties(compound.read("\x05SummaryInformation"))
    assert "Probna-Test" in found["Author"]


def test_an_empty_timestamp_is_absent_rather_than_1601(compound):
    """A FILETIME of zero is not a date in 1601. It is a field nobody set, and
    printing an epoch for it would be the tool inventing evidence."""
    found = read_properties(compound.read("\x05SummaryInformation"))
    assert "Create Time" not in found


def test_bytes_that_are_not_a_property_set_come_back_empty(compound):
    assert read_properties(b"not a property set at all") == {}


# The reader, and the one thing it must refuse to say.

from unmasker.detect import collect  # noqa: E402
from unmasker.readers import read  # noqa: E402


def test_a_word_97_file_is_dispatched_by_its_signature_not_its_name():
    assert read(SPECIMEN).kind == "doc"


def test_a_format_whose_text_is_unread_says_so_rather_than_reporting_none():
    """BIFF is not implemented, and a workbook must say that in those words.

    This assertion used to be made against the .doc. Word's text is read now,
    so the claim moved to a file it is still true of rather than being
    loosened to keep passing - which is how a report ends up describing a
    search that never happened.
    """
    extraction = read(WORKBOOK)
    assert extraction.text_unread is True
    assert extraction.has_text is False


def test_the_metadata_is_read_out_of_both_property_streams():
    fields = {f.name: f.value for f in read(SPECIMEN).metadata.fields}
    assert fields["Author"] == "Halina Probna-Test"
    assert fields["Company"] == "Osint Shifu sp. z o.o."


def test_nothing_is_called_undisclosed_when_nothing_was_compared():
    """The whole reason `text_unread` exists.

    Every content field is absent from a text that was never read, so without
    this the tool would report findings saying the document does not show
    values it was never asked about. A gap nobody looked for is not a gap.
    """
    found = collect(read(WORKBOOK))
    assert [f for f in found if f.detector == "undisclosed-metadata"] == []


def test_what_the_file_says_of_itself_is_still_put_in_front_of_a_reader():
    """Not a finding, and not silence either. A value this tool read and
    mentioned to nobody would be the worst of both."""
    remarks = " ".join(read(WORKBOOK).remarks)
    assert "Marek Zapasowy-Przyklad" in remarks
    assert "not compared" in remarks


def test_a_value_is_called_undisclosed_once_there_is_a_page_to_compare_it_to():
    """The other half of the same rule. The .doc names an author the page does
    not, and until its text was read this tool could not say so."""
    found = collect(read(SPECIMEN))
    undisclosed = [f for f in found if f.detector == "undisclosed-metadata"]
    assert any("Halina Probna-Test" in f.machine_reads for f in undisclosed)
    assert read(SPECIMEN).text_unread is False
