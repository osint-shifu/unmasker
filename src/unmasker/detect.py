"""Running every detector over one reading of one file.

This was inside `cli.py` while the command line was its only caller. The
directory survey is a second one, and a module that imports the command line to
borrow one function is a cycle waiting for the command line to import it back.

Nothing here decides how anything is printed. It answers *what does this file
disagree with itself about*, once, for whoever is asking.
"""

from __future__ import annotations

import dataclasses

from .attachments import detect_attachments
from .findings import Finding
from .metadata.detectors import detect as detect_metadata
from .pdf.detectors import detect as detect_drawn
from .pdf.detectors import unextractable_text, unrendered_text
from .pdf.history import detect as detect_earlier
from .pdf.rendered import read_page_back
from .revisions import detect as detect_revisions
from .sheets import detect as detect_sheets
from .slides import detect as detect_slides
from .text.invisible import scan_text
from .thumbnails import detect as detect_thumbnails
from .word.detectors import detect as detect_word


def collect(extraction, ocr: bool = False) -> list[Finding]:
    return _collect(extraction, ocr, descend=True)


def _inside(attachments: tuple) -> list[Finding]:
    """Everything a carried office package holds, read as a document itself.

    A spreadsheet inside a report hides a sheet exactly as one on disk does,
    and the file a person was sent is the one carrying it. Nothing was looking
    until now, here or anywhere else this project has seen.

    One level only. A package inside a package is not descended into, because
    a document that carries itself would otherwise be read forever, and the
    remark says so rather than letting the depth pass for coverage.
    """
    import tempfile
    from pathlib import Path

    from .readers import UnreadableFile
    from .readers import read as read_file

    found: list[Finding] = []
    for carried in attachments:
        if not carried.data:
            continue
        # A directory rather than `NamedTemporaryFile`: Windows will not let a
        # second handle open a named temporary that is still open, so the read
        # below failed there and the `except` swallowed it. Three CI jobs found
        # nothing and said nothing, which is the failure this tool is against.
        with tempfile.TemporaryDirectory(prefix="unmasker-carried-") as folder:
            written = Path(folder) / "carried"
            written.write_bytes(carried.data)
            try:
                inner = read_file(written)
            except UnreadableFile:
                # A zip this tool does not read as a document. That it is there
                # has already been said by `detect_attachments`.
                continue
            for finding in _collect(inner, ocr=False, descend=False):
                found.append(
                    dataclasses.replace(
                        finding,
                        location=dataclasses.replace(
                            finding.location, inside=carried.name
                        ),
                    )
                )
    return found


def _collect(extraction, ocr: bool = False, *, descend: bool = True) -> list[Finding]:
    """Run every text detector over every unit, tagging findings with the page.

    Detectors are additive and none outranks another: a unit with a bidi
    override and a homoglyph produces two findings, and nothing here filters
    one against the other.
    """
    found: list[Finding] = []
    for unit in extraction.units:
        for finding in scan_text(unit.text):
            if unit.page is not None:
                finding = dataclasses.replace(
                    finding,
                    location=dataclasses.replace(finding.location, page=unit.page),
                )
            found.append(finding)

    # Tier 1, for readers that can see what is painted. A page with a bar over
    # its text *and* a zero-width character in it has two findings, and neither
    # is allowed to suppress the other.
    for painted in extraction.drawn:
        found.extend(detect_drawn(painted))

    # Tier 4, for readers that can see what an application agreed not to show.
    if extraction.revisions is not None:
        found.extend(detect_revisions(extraction.revisions))

    # The same statement in a workbook: a row, a column or a sheet that carries
    # an attribute saying not to draw it, and every value in it still in the
    # file.
    if extraction.sheets is not None:
        found.extend(detect_sheets(extraction.sheets))

    # The same statement in a deck: a slide an application skips, and a note
    # that was never on the screen at all.
    if extraction.slides is not None:
        found.extend(detect_slides(extraction.slides))

    # And in a Word 97 document: a run carrying the hidden attribute, which
    # the application does not draw. Its tracked changes arrive through
    # `revisions` above, beside every other deletion this tool reports.
    if extraction.word is not None:
        found.extend(detect_word(extraction.word))

    # A photograph, against the smaller photograph inside it. The shape
    # comparison is free; reading the preview back costs an OCR pass and waits
    # for --ocr, like everything else that renders.
    if extraction.image is not None and extraction.source is not None:
        pictured, problems = detect_thumbnails(extraction.source, extraction.image, ocr=ocr)
        found.extend(pictured)
        extraction = dataclasses.replace(
            extraction, remarks=extraction.remarks + tuple(problems)
        )

    # Reading each page back costs a render and an OCR pass - seconds a page -
    # and needs two external binaries, which is why it was kept out
    # of the first version and is still off unless asked for.
    if ocr and extraction.source is not None:
        for painted in extraction.drawn:
            words, problems = read_page_back(extraction.source, painted.number, painted.box)
            extraction = dataclasses.replace(
                extraction, remarks=extraction.remarks + tuple(problems)
            )
            found.extend(unrendered_text(painted, words))
            found.extend(unextractable_text(painted, words))

    # Everything the current catalogue stopped pointing at. A PDF is appended
    # to rather than rewritten, so an edit leaves what it replaced in the file.
    if extraction.earlier:
        shown = "\n".join(unit.text for unit in extraction.units)
        found.extend(detect_earlier(extraction.earlier, shown))

    # A whole file carried inside this one. Not a hiding technique - an
    # attachment is a feature - but it is content the page does not mention,
    # which is the same statement as every other detector here.
    if extraction.attachments:
        found.extend(detect_attachments(extraction.attachments))
        # Saying a workbook is there and reading what is in it are two
        # findings, not a ranking. Both are reported.
        if descend:
            found.extend(_inside(extraction.attachments))

    # Metadata is only a finding where it says something the document does not,
    # so the detector is given the document's own text to compare against.
    if extraction.metadata is not None:
        shown = "\n".join(unit.text for unit in extraction.units)
        found.extend(
            detect_metadata(
                extraction.metadata, shown, comparable=not extraction.text_unread
            )
        )

    return sorted(found, key=lambda f: f.location.sort_key)
