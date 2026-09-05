"""Shared fixtures: the committed specimens, and stub resources for unit tests.

The stubs stand in for pypdf's object model in tests that need a form or an
image without a whole PDF around it. They are deliberately thin - a dict that
answers `get_object()` - because anything richer would start testing the stub.
"""

from pathlib import Path

import pytest
from pypdf import PdfReader

SPECIMENS = Path(__file__).parent / "specimens"

SPECIMEN_PDF = [
    "libreoffice-writer-black-bars.pdf",
    "chrome-print-css-overlay.pdf",
    "libreoffice-writer-properly-redacted.pdf",
    "flattened-to-image.pdf",
]


def page_of(name: str, index: int = 0):
    """Page `index` of a committed specimen, as a pypdf page."""
    return PdfReader(str(SPECIMENS / "pdf" / name)).pages[index]


def font_of(specimen: str, resource: str, index: int = 0):
    """One font dictionary out of a committed specimen, by resource name.

    Real font dictionaries rather than stubs, because the two specimens carry
    the two width tables that matter - `/Widths` and `/W` - and a stub would
    only prove the parser agrees with whoever wrote the stub.
    """
    page = page_of(specimen, index)
    return page["/Resources"]["/Font"][resource].get_object()


class Stub(dict):
    """A dictionary that behaves enough like a pypdf object to be resolved."""

    def get_object(self):
        return self


class StubStream(Stub):
    def __init__(self, data: bytes, **entries):
        super().__init__(**entries)
        self._data = data

    def get_data(self) -> bytes:
        return self._data


#: A case folder, assembled from committed specimens rather than committed as a
#: second copy of them.
#:
#: The files are still real producer output - that is what the aggregation is
#: being tested against - and building the folder at test time avoids 800 KB of
#: duplicates and the symlinks that would not survive the Windows CI job.
#:
#: Chosen so the survey has something to say in every section: files that hide
#: something in three different containers, a control that must stay silent, a
#: nested directory, a dotfile that must be skipped, and two files that cannot
#: be read for two different reasons.
CASE_FOLDER = {
    "bids.xlsx": "xlsx/libreoffice-calc-hidden-columns.xlsx",
    "minutes.pdf": "pdf/libreoffice-writer-black-bars.pdf",
    "position-note.odt": "odf/libreoffice-writer-position-note.odt",
    "clean.pdf": "pdf/libreoffice-writer-properly-redacted.pdf",
    "sub/settlement.docx": "docx/libreoffice-writer-tracked-changes.docx",
}


@pytest.fixture
def case_folder(tmp_path):
    """A directory a survey can be run against, and what is in it."""
    import shutil

    for name, source in CASE_FOLDER.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SPECIMENS / source, target)

    # Two refusals, for two different reasons: one the tool recognises and
    # explains, one it simply does not read. A real zip, because a broken one
    # would be refused for being broken and would test nothing.
    import zipfile

    with zipfile.ZipFile(tmp_path / "deck.pptx", "w") as deck:
        deck.writestr("[Content_Types].xml", "<Types/>")
        deck.writestr("ppt/presentation.xml", "<presentation/>")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" * 4)

    # Never walked into: a case folder under version control would otherwise
    # have its whole object store surveyed.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / ".hidden.pdf").write_bytes(b"%PDF-1.4 not really")

    return tmp_path


@pytest.fixture
def form_resources():
    """A form XObject that draws a 10x10 square under its own doubling matrix."""
    return Stub(
        XObject=Stub(
            Fm0=StubStream(
                b"0 0 0 rg 0 0 10 10 re f",
                Subtype="/Form",
                Matrix=[2, 0, 0, 2, 0, 0],
                BBox=[0, 0, 100, 100],
            )
        )
    )


@pytest.fixture
def cyclic_resources():
    """A form that draws itself. Real files contain these, by accident."""
    form = StubStream(b"/Fm0 Do", Subtype="/Form", BBox=[0, 0, 100, 100])
    resources = Stub(XObject=Stub(Fm0=form))
    form["Resources"] = resources
    return resources


@pytest.fixture
def image_resources():
    return Stub(
        XObject=Stub(
            Im0=StubStream(b"", Subtype="/Image", Width=4, Height=4),
        )
    )
