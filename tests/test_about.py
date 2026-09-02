"""The screen a bare `unmasker` prints.

A landing screen is the one piece of output nobody re-reads and everybody sees
once, which is exactly the shape of a thing that goes stale without anyone
noticing. These tests hold the two ways it can lie - by overstating what the
tool does, and by drawing outside the width it just declared - and the one way
it can stop being unmasker's, by losing the mark.
"""

from __future__ import annotations

import re
from pathlib import Path

from unmasker import about
from unmasker.cli import main
from unmasker.report import Style
from unmasker.theme import Depth

SOURCE = Path(__file__).resolve().parent.parent / "src" / "unmasker"


class _AsciiOnly:
    """A stream that says it can only encode ASCII. `io.StringIO` will not let
    its `encoding` be set, and a stub is thinner than a real file anyway."""

    encoding = "ascii"


def screen(**kwargs) -> str:
    return about.render(Style(depth=Depth.NONE, width=kwargs.pop("width", 78), **kwargs))


# --------------------------------------------------------------------------
# the mark
# --------------------------------------------------------------------------


def test_the_mark_is_a_bar_that_did_not_cover_the_word():
    """The whole identity in two lines: five blocks over `unmas`, and `ker`
    still readable. If the bar ever covered the word completely the mark would
    be a black rectangle, which is the one thing this tool is against."""
    covered, underneath = about.mark(None)
    assert underneath == "unmasker"
    assert covered.endswith("ker")
    assert covered != underneath
    assert len(covered) == len(underneath), "the two lines must register"


def test_the_mark_falls_back_where_a_block_cannot_be_encoded():
    """A terminal that cannot print a block gets the same layout in a
    character it can - never a different layout."""
    covered, underneath = about.mark(_AsciiOnly())
    assert covered == "#####ker"
    assert len(covered) == len(underneath)
    covered.encode("ascii")


def test_the_screen_opens_with_the_mark():
    lines = [line for line in screen().splitlines() if line.strip()]
    assert lines[0].strip().endswith("ker")
    assert lines[1].strip().startswith("unmasker")


# --------------------------------------------------------------------------
# it must not overstate the tool
# --------------------------------------------------------------------------


def test_the_detector_count_matches_the_source():
    """The first number a reader can check. A screen that claims more
    detectors than exist is the tool's own front door contradicting it."""
    slugs: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        text = path.read_text()
        slugs |= set(re.findall(r'detector="([a-z-]+)"', text))
        slugs |= set(re.findall(r'^\s+"([a-z]+-[a-z]+(?:-[a-z]+)?)",$', text, re.M))
        slugs |= set(re.findall(r'_under\(page, \([^)]*\), "([a-z-]+)"', text))
    assert about.DETECTORS == len(slugs), (
        f"the screen says {about.DETECTORS}, the source has {len(slugs)}"
    )


def test_every_format_it_claims_to_open_is_named_in_the_dispatch():
    """`opens PDF · DOCX · ODT · XLSX · ODS · text` has to be true of the
    reader, not of an intention."""
    dispatch = (SOURCE / "readers" / "__init__.py").read_text()
    claimed = dict(about.READS)["opens"]
    assert "word/document.xml" in dispatch and "DOCX" in claimed
    assert "xl/workbook.xml" in dispatch and "XLSX" in claimed
    assert "content.xml" in dispatch and "ODS" in claimed


def test_it_says_presentations_are_refused():
    """The one thing a reader is most likely to try and be surprised by."""
    refused = dict(about.READS)["refuses"]
    assert ".pptx" in refused and ".odp" in refused
    assert "NO_SLIDES" in (SOURCE / "readers" / "__init__.py").read_text()


def test_the_exit_codes_on_the_screen_are_the_ones_the_cli_returns():
    codes = dict(about.RUNNING)["exit status"]
    assert "0 nothing found" in codes
    assert "1 findings exist" in codes
    assert "2 could not be read" in codes


# --------------------------------------------------------------------------
# it must not draw outside the width it declared
# --------------------------------------------------------------------------


def test_no_line_runs_past_the_rule():
    """The rule is drawn to the declared width, and a line overshooting it is
    the first thing a reader sees. `report.py` holds the report to this; the
    front door is the easier place to forget."""
    for width in (50, 62, 78, 100):
        for line in about.render(Style(depth=Depth.NONE, width=width)).splitlines():
            assert len(line) <= width, f"{len(line)} > {width}: {line!r}"


def test_a_narrow_terminal_still_gets_every_section():
    narrow = about.render(Style(depth=Depth.NONE, width=50))
    for heading in ("looks at", "reads", "running it"):
        assert heading in narrow


# --------------------------------------------------------------------------
# what a bare run does
# --------------------------------------------------------------------------


def test_a_bare_run_prints_the_screen_and_exits_zero(capsys):
    """Not exit 2. Nothing was read and nothing failed to be read - the tool
    introduced itself, which is not an error and not a result."""
    assert main([]) == 0
    assert "unmasker" in capsys.readouterr().out


def test_a_bare_run_makes_no_claim_about_any_file(capsys):
    """A screen that shows output can be mistaken for output. This one must
    not say it searched, found or read anything."""
    main([])
    printed = capsys.readouterr().out
    for claim in ("searched", "nothing hidden found", "findings in"):
        assert claim not in printed
