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
