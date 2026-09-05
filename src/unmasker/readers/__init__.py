"""Turning a file into text, and saying how much text there was to turn.

Dispatch is by content, not by extension. A `.txt` holding a PDF is a PDF, and
a forensic tool that trusts a filename has already been fooled once.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from .docx import read_docx
from .image import read_image
from .legacy import read_legacy
from .model import Extraction, TextUnit, UnreadableFile
from .odf import read_odf
from .pdf import read_pdf
from .plain import read_plain
from .presentation import read_odp, read_pptx
from .spreadsheet import odf_flavour, read_ods, read_xlsx

__all__ = ["Extraction", "TextUnit", "UnreadableFile", "read"]

def _digest(path: Path) -> str:
    """sha256 of the file, read in blocks so a large one costs no memory.

    Failure is empty rather than fatal: the digest annotates a report, and a
    file that could be read for its contents and not for its bytes is a case
    worth reporting anyway.
    """
    try:
        block = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                block.update(chunk)
        return block.hexdigest()
    except OSError:
        return ""


#: How large a carried file may be before its bytes are left where they are.
#: Reading it is how this tool finds a hidden sheet inside a document; holding
#: an embedded video to discover it is a video is not worth the memory.
HOLD = 32 * 1024 * 1024


def _embedded(path: Path) -> tuple:
    """Whole files an office package carries as members.

    Both families do this and neither hides it: an embedded object is *on* the
    page. What is on the page is a picture of it - LibreOffice writes an EMF
    beside the object for exactly that purpose - and the file the picture was
    made from travels with the document. That is the finding, and it is a
    different one from a PDF attachment.

    OOXML keeps each object as one member under `*/embeddings/`. OpenDocument
    keeps it as a sub-package, `Object 1/` and everything beneath, so those are
    gathered into one record rather than reported a member at a time.
    `ObjectReplacements/` is skipped: that is the picture, not the object.
    """
    import zipfile

    from .model import Attachment, describe_bytes

    found = []
    packages: dict[str, list[int]] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                parts = entry.filename.split("/")
                if len(parts) > 2 and parts[1] == "embeddings" and parts[-1]:
                    with archive.open(entry) as handle:
                        head = handle.read(8)
                    # Only a zip is worth holding: it is the only carried thing
                    # this tool can read, and the cap keeps an embedded video
                    # out of memory.
                    keep = head.startswith(b"PK\x03\x04") and entry.file_size <= HOLD
                    found.append(
                        Attachment(
                            name=parts[-1],
                            size=entry.file_size,
                            part=entry.filename,
                            description=describe_bytes(head),
                            data=archive.read(entry) if keep else None,
                        )
                    )
                elif parts[0].startswith("Object ") and len(parts) > 1 and parts[-1]:
                    seen = packages.setdefault(parts[0], [0, 0])
                    seen[0] += entry.file_size
                    seen[1] += 1
    except (OSError, zipfile.BadZipFile):
        return ()

    for package, (size, count) in packages.items():
        found.append(
            Attachment(
                name=f"{package}/",
                size=size,
                part=f"{package}/",
                # A sub-package has no first bytes of its own; what it is, is
                # the thing it is made of.
                description=f"a sub-package of {count} members, itself a document",
            )
        )

    return tuple(found)


def read(path: str | Path) -> Extraction:
    """Read `path` into text units, or raise `UnreadableFile`."""
    path = Path(path)
    try:
        head = path.open("rb").read(8)
    except OSError as exc:
        raise UnreadableFile(f"cannot open {path}: {exc}") from exc

    # Attached once here rather than in each reader, so a format added later
    # cannot arrive without it.
    extraction = dataclasses.replace(_dispatch(path, head), sha256=_digest(path))

    # The PDF reader fills these itself, because the name tree is pypdf's to
    # walk. Every zip container is read the same way here for the same reason
    # the digest is.
    if not extraction.attachments and head.startswith(b"PK\x03\x04"):
        extraction = dataclasses.replace(extraction, attachments=_embedded(path))
    return extraction


def _dispatch(path: Path, head: bytes) -> Extraction:
    if head.startswith(b"%PDF-"):
        return read_pdf(path)
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return read_legacy(path)
    if head.startswith(b"\xff\xd8\xff"):
        return read_image(path)
    if head.startswith(b"PK\x03\x04"):
        # Every OOXML and ODF file is a zip. Which one it is depends on what is
        # inside, so the contents decide - not the extension, which a forensic
        # tool has no business trusting.
        return _read_zip(path)
    return read_plain(path)


def _read_zip(path: Path) -> Extraction:
    """An OOXML document, an OpenDocument one, or neither."""
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise UnreadableFile(f"{path.name} is not a readable zip: {exc}") from exc

    if "word/document.xml" in names:
        return read_docx(path)
    if "xl/workbook.xml" in names:
        return read_xlsx(path)
    if "ppt/presentation.xml" in names:
        return read_pptx(path)
    if "content.xml" in names:
        # Every OpenDocument file is a `content.xml`, and until the flavour is
        # asked for they all look like text documents. Sending a spreadsheet to
        # the text reader is not a near miss: it reads the hidden rows and
        # columns as visible prose and then reports the workbook clean.
        with zipfile.ZipFile(path) as archive:
            flavour = odf_flavour(archive)
        if flavour == "spreadsheet":
            return read_ods(path)
        if flavour == "presentation":
            return read_odp(path)
        return read_odf(path)
    raise UnreadableFile(
        f"{path.name} is a zip but not a document unmasker reads: it holds "
        "no Word document, workbook or OpenDocument body"
    )
