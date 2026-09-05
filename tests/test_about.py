"""The screen a bare `unmasker` prints.

A landing screen is the one piece of output nobody re-reads and everybody sees
once, which is exactly the shape of a thing that goes stale without anyone
noticing. These tests hold the three ways it can go wrong: by offering a flag
or an example that does not work, by drawing wider than it should, and by
losing the mark that makes it this tool's screen rather than any tool's.
"""

from __future__ import annotations

from pathlib import Path

from unmasker import about
from unmasker.cli import build_parser, main
from unmasker.report import Style
from unmasker.theme import Depth

SOURCE = Path(__file__).resolve().parent.parent / "src" / "unmasker"

SECTIONS = ("USAGE", "OPTIONS", "EXAMPLES", "EXIT STATUS", "FORMATS")


class _AsciiOnly:
    """A stream that says it can only encode ASCII. `io.StringIO` will not let
    its `encoding` be set, and a stub is thinner than a real file anyway."""

    encoding = "ascii"


def screen(width: int = 78) -> str:
    return about.render(Style(depth=Depth.NONE, width=width))


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
    assert lines[0].endswith("ker")
    assert lines[1].startswith("unmasker")


# --------------------------------------------------------------------------
# every command it prints has to work
#
# `CONTRIBUTING.md`: every command the tool prints must run in the shell that
# printed it. A landing screen is the worst place to break that, because it is
# the first thing anybody tries.
# --------------------------------------------------------------------------


def test_every_option_on_the_screen_is_a_real_flag():
    known = set()
    for action in build_parser()._actions:
        known.update(action.option_strings)

    for name, _ in about.OPTIONS:
        for flag in (part.strip() for part in name.split(",")):
            flag = flag.split()[0]  # `--width N` -> `--width`
            assert flag in known, f"the screen offers {flag}, the parser has no such flag"


def test_every_example_parses():
    """Not merely that the flags exist - that the whole line is accepted."""
    parser = build_parser()
    for command, _ in about.EXAMPLES:
        argv = command.split()
        assert argv[0] == "unmasker", command
        parser.parse_args(argv[1:])


def test_the_exit_codes_are_the_ones_the_cli_returns(tmp_path, capsys):
    """The screen lists three. Each one is produced here rather than trusted."""
    listed = {code for code, _ in about.EXIT}
    assert listed == {"0", "1", "2"}

    specimens = Path(__file__).parent / "specimens" / "pdf"
    assert main([str(specimens / "libreoffice-writer-properly-redacted.pdf")]) == 0
    assert main([str(specimens / "libreoffice-writer-black-bars.pdf")]) == 1
    assert main([str(tmp_path / "no-such-file")]) == 2
    capsys.readouterr()


def test_the_formats_it_names_are_the_ones_the_reader_dispatches_on():
    dispatch = (SOURCE / "readers" / "__init__.py").read_text()
    assert "word/document.xml" in dispatch and "DOCX" in about.FORMATS
    assert "xl/workbook.xml" in dispatch and "XLSX" in about.FORMATS
    assert "content.xml" in dispatch and "ODS" in about.FORMATS


def test_it_says_presentations_are_refused():
    """The first surprise a reader can have is pointing this at a deck."""
    assert "refused" in about.FORMATS.lower()
    assert "NO_SLIDES" in (SOURCE / "readers" / "__init__.py").read_text()


# --------------------------------------------------------------------------
# it must not sprawl
# --------------------------------------------------------------------------


def test_it_lays_out_narrow_however_wide_the_terminal_is():
    """The report draws to the width it measured because its values wrap. A
    help screen's content is short and fixed, so stretching it to a very wide
    terminal leaves each description marooned from the flag it belongs to."""
    for line in screen(width=200).splitlines():
        assert len(line) <= about.WIDTH, f"{len(line)} > {about.WIDTH}: {line!r}"


def test_no_line_runs_past_a_narrow_terminal():
    for width in (40, 50, 62, 78):
        for line in screen(width=width).splitlines():
            assert len(line) <= width, f"{len(line)} > {width}: {line!r}"


def test_a_narrow_terminal_still_gets_every_section():
    narrow = screen(width=40)
    for heading in SECTIONS:
        assert heading in narrow


def test_the_sections_are_the_classic_ones_and_in_order():
    """Flush-left capitals, in the order every modern command-line tool uses.
    A reader who has used `gh` or `rg` should not have to learn this one."""
    text = screen()
    positions = [text.index(f"\n{heading}\n") for heading in SECTIONS]
    assert positions == sorted(positions)


def test_there_are_no_rules_or_boxes():
    """The report has a rule under its masthead because it has sections of
    findings to separate. A help screen has headings, and drawing a line under
    each one is furniture."""
    assert "─" not in screen()
    assert "│" not in screen()


# --------------------------------------------------------------------------
# what a bare run does
# --------------------------------------------------------------------------


def test_a_bare_run_prints_the_screen_and_exits_zero(capsys):
    """Not exit 2. Nothing was read and nothing failed to be read - the tool
    introduced itself, which is neither an error nor a result."""
    assert main([]) == 0
    assert "USAGE" in capsys.readouterr().out


def test_a_bare_run_makes_no_claim_about_any_file(capsys):
    """A screen that shows output can be mistaken for output, so this one must
    not carry a phrase the report uses to describe a reading.

    It is the report's own sentences that are forbidden, not the word
    `searched` - the exit-status legend has every right to say what 0 means.
    """
    main([])
    printed = capsys.readouterr().out
    for claim in (
        "searched the text of this file",
        "nothing hidden found",
        "nothing to search",
        "finding in",
        "findings in",
    ):
        assert claim not in printed
