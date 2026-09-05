"""Anything that is already text: TXT, Markdown, HTML, source code, CSV.

Tier 2 needs nothing else from these files. The characters it hunts are in the
bytes, and no container has to be understood first.
"""

from __future__ import annotations

from pathlib import Path

from .model import Extraction, TextUnit, UnreadableFile


def read_plain(path: Path) -> Extraction:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UnreadableFile(f"cannot read {path}: {exc}") from exc

    if b"\x00" in raw:
        raise UnreadableFile(
            f"{path.name} contains null bytes and is not text; "
            "unmasker reads PDF, DOCX, ODT, XLSX, ODS and text files"
        )

    try:
        # Deliberately not `utf-8-sig`. A byte-order mark is a character this
        # tool has an opinion about: leading is how the file was saved, and
        # anywhere else is a finding. Stripping it here would throw the
        # evidence away before the detector ever saw it.
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnreadableFile(
            f"{path.name} is not valid UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc

    remarks: tuple[str, ...] = ()
    if not text.strip():
        remarks = (
            "the file holds no text, so there was nothing to search"
            if not text
            else "the file holds only whitespace, so there was nothing to search",
        )

    return Extraction(kind="plain", units=(TextUnit(text=text),), remarks=remarks)
