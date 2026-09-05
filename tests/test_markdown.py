"""The report as Markdown.

The same three-readers split as the HTML: the terminal triages, `--json` is the
pipeline's archive, `--html` is the page you attach to an email, and this is
the one that goes into a wiki, a ticket, a pull request or a notebook - places
that already speak Markdown and where an HTML attachment is the wrong shape.

## Markdown is the more dangerous of the two

An HTML renderer that is handed `<script>` prints it, because this tool escapes
it. A **Markdown** renderer that is handed `<script>` runs it, because passing
raw HTML through is what Markdown does - on GitHub, in a wiki, in every editor
preview.

So the escaping here is not the HTML rules translated. It is a different set of
rules for a format that is more permissive, and it has to hold for three kinds
of damage:

- **raw HTML**, which becomes live markup wherever this is rendered
- **`|`**, which silently breaks a table row into different cells
- **backticks, asterisks and underscores**, which turn somebody else's text
  into somebody else's formatting

Every one of those arrived in a document written by whoever is being
investigated.
"""

from __future__ import annotations

import re
from pathlib import Path

from unmasker.detect import collect
from unmasker.findings import Basis, Finding, Location
from unmasker.markdown import render_file, render_survey
from unmasker.readers import read
from unmasker.scan import survey

SPECIMENS = Path(__file__).parent / "specimens"
BARS = SPECIMENS / "pdf" / "libreoffice-writer-black-bars.pdf"


def page_md(path=BARS) -> str:
    extraction = read(path)
    return render_file(path, extraction, collect(extraction))


def _hostile(**kwargs) -> Finding:
    base = dict(
        detector="undisclosed-metadata",
        basis=Basis.SELF_REPORTED,
        summary="a field the document does not show",
        human_sees="",
        machine_reads="ordinary",
        location=Location(page=1),
    )
    return Finding(**{**base, **kwargs})


def _extraction(remarks=()):
    from unmasker.readers.model import Extraction, TextUnit

    return Extraction(kind="pdf", units=(TextUnit(text="something"),), remarks=remarks)


# --------------------------------------------------------------------------
# hostile input, which is the only input this tool has
# --------------------------------------------------------------------------


def test_raw_html_in_a_value_cannot_become_markup():
    """A Markdown renderer passes raw HTML through, which makes this the more
    dangerous of the two formats rather than the safer one."""
    payload = "<img src=x onerror=alert(1)>"
    out = render_file(Path("evil.pdf"), _extraction(), [_hostile(machine_reads=payload)])
    # It has to be reported - the value is the evidence - and it has to be
    # inside a fence, where nothing is markup. Asserting the characters are
    # absent would be asserting the tool lost the finding.
    assert payload in out
    assert payload in "\n".join(_fenced(out))


def test_raw_html_in_a_summary_cannot_become_markup():
    out = render_file(
        Path("evil.pdf"), _extraction(), [_hostile(summary="<script>alert(1)</script>")]
    )
    assert "<script>" not in out


def test_a_pipe_cannot_break_a_table():
    """A value with a `|` in it would silently split one cell into two and
    every column after it would be reporting the wrong thing."""
    out = render_survey_of(machine_reads="a | b | c")
    for line in out.splitlines():
        if line.startswith("|"):
            assert line.count("|") % 2 == 1 or "\\|" in line or "`" in line


def test_formatting_characters_do_not_become_formatting():
    """`*` and `_` in somebody else's filename are not emphasis."""
    payload = "*not bold* _not italic_"
    out = render_file(Path("evil.pdf"), _extraction(), [_hostile(machine_reads=payload)])
    assert payload in "\n".join(_fenced(out))


def test_a_backtick_in_a_value_does_not_end_the_code_span():
    """The one character that can escape a code fence from inside it."""
    out = render_file(
        Path("evil.pdf"), _extraction(), [_hostile(machine_reads="a ` b ``` c")]
    )
    assert "a ` b ``` c" in out
    # whatever fence was chosen, it is longer than the run inside it
    fences = re.findall(r"^(`{3,})", out, re.M)
    assert not fences or max(len(f) for f in fences) >= 4


def test_a_remark_cannot_become_markup():
    out = render_file(Path("x.pdf"), _extraction(remarks=("<b>not bold</b>",)), [])
    assert not re.search(r"^<b>", out, re.M)


def test_a_file_name_cannot_become_markup():
    out = render_file(Path("<script>x</script>.pdf"), _extraction(), [])
    assert "<script>" not in out


def _fenced(markdown: str) -> list[str]:
    """Everything inside a fenced block, where nothing is markup.

    The fence is tracked as its run of backticks rather than the whole opening
    line: the opener carries a language tag and the closer does not.
    """
    out: list[str] = []
    fence: str | None = None
    for line in markdown.splitlines():
        ticks = re.match(r"`{3,}", line)
        if fence is None:
            if ticks:
                fence = ticks.group(0)
            continue
        if ticks and ticks.group(0) == fence and line.strip() == fence:
            fence = None
            continue
        out.append(line)
    return out


def render_survey_of(**kwargs) -> str:
    return render_file(Path("x.pdf"), _extraction(), [_hostile(**kwargs)])


# --------------------------------------------------------------------------
# it says what the other reports say
# --------------------------------------------------------------------------


def test_it_carries_both_readings():
    out = page_md()
    assert "human sees" in out
    assert "machine reads" in out
    assert "w.testowa@example.org" in out


def test_it_names_the_evidence_class_in_words():
    out = page_md()
    assert "direct" in out


def test_it_names_every_detector():
    assert "covered-text" in page_md()


def test_no_word_of_judgement_appears():
    out = page_md().lower()
    for word in ("severity", "critical", "risk", "score", "suspicious", "dangerous"):
        assert word not in out


def test_a_document_with_nothing_hidden_says_which_nothing_it_means():
    control = SPECIMENS / "pdf" / "libreoffice-writer-properly-redacted.pdf"
    extraction = read(control)
    out = render_file(control, extraction, collect(extraction))
    assert "searched" in out.lower()


# --------------------------------------------------------------------------
# the survey
# --------------------------------------------------------------------------


def test_the_survey_carries_the_full_detail(case_folder):
    out = render_survey(survey(case_folder))
    assert "hidden-rows" in out
    assert "196000" in out or "Reserve price" in out


def test_the_survey_lists_what_could_not_be_read(case_folder):
    out = render_survey(survey(case_folder))
    assert "attachments.zip" in out and "photo.jpg" in out


def test_the_survey_does_not_rank(case_folder):
    out = render_survey(survey(case_folder))
    names = ["bids.xlsx", "minutes.pdf", "position-note.odt"]
    assert [out.index(n) for n in names] == sorted(out.index(n) for n in names)


def test_a_survey_of_unreadable_files_never_says_nothing_was_found(tmp_path):
    for name in ("a.jpg", "b.jpg"):
        (tmp_path / name).write_bytes(b"\xff\xd8\xff\xe0nope")
    out = render_survey(survey(tmp_path))
    assert "nothing hidden found" not in out.lower()


# --------------------------------------------------------------------------
# it has to be Markdown
# --------------------------------------------------------------------------


def test_it_opens_with_a_heading():
    assert page_md().startswith("# ")


def test_every_table_row_has_the_columns_its_header_declares(case_folder):
    """A table whose rows disagree with its header renders as garbage in every
    viewer, and silently."""
    out = render_survey(survey(case_folder))
    header = None
    for line in out.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = line.count("|") - line.count("\\|")
        if header is None:
            header = cells
        else:
            assert cells == header, f"row has {cells} cells, header has {header}: {line!r}"


# --------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------


def test_md_goes_to_stdout(capsys):
    from unmasker.cli import main

    assert main([str(BARS), "--md"]) == 1
    assert capsys.readouterr().out.startswith("# ")


def test_md_works_on_a_directory(case_folder, capsys):
    from unmasker.cli import main

    assert main([str(case_folder), "--md"]) == 1
    assert "bids.xlsx" in capsys.readouterr().out


def test_only_one_output_shape_at_a_time(capsys):
    """Two of them down one pipe is one of them corrupted."""
    from unmasker.cli import main

    for pair in (["--md", "--json"], ["--md", "--html"], ["--html", "--json"]):
        assert main([str(BARS), *pair]) == 2
        assert capsys.readouterr().err.strip()
