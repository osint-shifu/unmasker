"""Running every detector over one reading of one file.

This was inside `cli.py` while the command line was its only caller. The
directory survey is a second one, and a module that imports the command line to
borrow one function is a cycle waiting for the command line to import it back.

Nothing here decides how anything is printed. It answers *what does this file
disagree with itself about*, once, for whoever is asking.
"""

from __future__ import annotations

import dataclasses

from .findings import Finding
from .metadata.detectors import detect as detect_metadata
from .pdf.detectors import detect as detect_drawn
from .pdf.detectors import unextractable_text, unrendered_text
from .pdf.rendered import read_page_back
from .revisions import detect as detect_revisions
from .sheets import detect as detect_sheets
from .slides import detect as detect_slides
from .text.invisible import scan_text
from .thumbnails import detect as detect_thumbnails


def collect(extraction, ocr: bool = False) -> list[Finding]:
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

    # Metadata is only a finding where it says something the document does not,
    # so the detector is given the document's own text to compare against.
    if extraction.metadata is not None:
        shown = "\n".join(unit.text for unit in extraction.units)
        found.extend(detect_metadata(extraction.metadata, shown))

    return sorted(found, key=lambda f: f.location.sort_key)
