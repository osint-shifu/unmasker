"""The report as a file somebody can send.

The terminal report triages, `--json` is the archive a pipeline reads, and this
is the archive a person reads - the one that gets attached to an email and
opened by a lawyer, an editor, or a court clerk who has nothing installed.

That audience decides everything about it. It is one self-contained file with
no external anything, it carries the full detail rather than a summary because
a browser has search and a scrollbar where a terminal has neither, and it is
built to survive being printed.

## The test that matters most

`SECURITY.md` says this tool parses hostile files by design. Everything it
quotes came out of a document somebody else wrote, and putting that into HTML
is exactly where a document gets to run code in the reader's browser.

So the escaping tests are not hygiene here. They are the feature.
"""

from __future__ import annotations

import re
from pathlib import Path

from unmasker.detect import collect
from unmasker.findings import Basis, Finding, Location
from unmasker.html import render_file, render_survey
from unmasker.readers import read
from unmasker.scan import survey

SPECIMENS = Path(__file__).parent / "specimens"
BARS = SPECIMENS / "pdf" / "libreoffice-writer-black-bars.pdf"


def page_html(path=BARS) -> str:
    extraction = read(path)
    return render_file(path, extraction, collect(extraction))


# --------------------------------------------------------------------------
# hostile input, which is the only input this tool has
# --------------------------------------------------------------------------


def test_a_finding_that_contains_markup_is_not_markup():
    """A document whose metadata reads `<script>...` would otherwise put a live
    script into the report of itself. Everything quoted here came out of a file
    somebody else wrote."""
    hostile = Finding(
        detector="undisclosed-metadata",
        basis=Basis.SELF_REPORTED,
        summary="<script>alert(1)</script>",
        human_sees="<img src=x onerror=alert(2)>",
        machine_reads="</td></tr><script>alert(3)</script>",
        location=Location(page=1),
    )
    out = render_file(Path("evil.pdf"), _extraction(), [hostile])
    # The test is whether the markup can form, not whether the characters
    # appear: `onerror=` is harmless text once the `<` before it is escaped,
    # and asserting its absence would be watching the wrong thing.
    assert "<script>" not in out
    assert "<img" not in out
    assert "</td>" not in out
    assert "&lt;script&gt;" in out
    assert "&lt;img" in out


def test_a_file_name_that_contains_markup_is_not_markup():
    out = render_file(Path("<script>alert(1)</script>.pdf"), _extraction(), [])
    assert "<script>alert" not in out


def test_a_remark_that_contains_markup_is_not_markup():
    out = render_file(Path("x.pdf"), _extraction(remarks=("<b>not bold</b>",)), [])
    assert "<b>not bold</b>" not in out
    assert "&lt;b&gt;" in out


def test_there_is_no_script_anywhere():
    """No JavaScript at all. An attachment opened in a law office should not be
    asking anybody to trust it."""
    out = page_html()
    assert "<script" not in out.lower()
    assert "javascript:" not in out.lower()
    assert not re.search(r"\son\w+\s*=", out), "an inline event handler got in"


def test_nothing_is_loaded_from_anywhere_else():
    """Self-contained: it has to open from an email attachment, offline."""
    out = page_html()
    assert "http://" not in out
    assert "https://" not in out
    assert "<link" not in out.lower()
    assert re.search(r"<img[^>]", out) is None


# --------------------------------------------------------------------------
# it says what the terminal says
# --------------------------------------------------------------------------


def test_it_carries_both_readings_of_every_finding():
    out = page_html()
    assert "human sees" in out
    assert "machine reads" in out
    assert "w.testowa@example.org" in out


def test_it_names_the_evidence_class_in_words():
    """`CONTRIBUTING.md`: a word a reader can argue with, never a number.

    The check is on the document's text rather than its source: this module's
    own CSS has a `border-radius: 50%` in it, and a test that scanned the
    stylesheet would be watching the wrong half of the file.
    """
    out = _text(page_html())
    assert "direct" in out
    assert "%" not in out


def test_it_names_the_detector_for_every_finding():
    out = page_html()
    assert "covered-text" in out


def test_a_document_with_nothing_hidden_says_which_nothing_it_means():
    """Searched and found nothing is not the same as nothing to search, and
    the file that gets filed has to say which one it met."""
    control = SPECIMENS / "pdf" / "libreoffice-writer-properly-redacted.pdf"
    extraction = read(control)
    out = render_file(control, extraction, collect(extraction))
    assert "searched" in out.lower()


def test_no_word_of_judgement_appears():
    out = _text(page_html()).lower()
    for word in ("severity", "critical", "risk", "score", "suspicious", "dangerous"):
        assert word not in out


# --------------------------------------------------------------------------
# the survey, which is the one somebody hands over
# --------------------------------------------------------------------------


def test_the_survey_carries_the_full_detail_not_a_summary(case_folder):
    """The terminal triages because a scroll is unreadable. A browser has
    search and a scrollbar, so this is where the whole record goes."""
    out = render_survey(survey(case_folder))
    assert "hidden-rows" in out
    assert "Reserve price" in out or "196000" in out


def test_the_survey_lists_what_could_not_be_read(case_folder):
    out = render_survey(survey(case_folder))
    assert "deck.pptx" in out
    assert "photo.jpg" in out
    assert "presentation" in out


def test_the_survey_links_the_overview_to_the_detail(case_folder):
    """A hundred files is a document you navigate, not one you scroll."""
    out = render_survey(survey(case_folder))
    for anchor in re.findall(r'href="#([^"]+)"', out):
        assert f'id="{anchor}"' in out, f"a link points at #{anchor}, which is nowhere"
    assert re.search(r'href="#', out), "the overview links nowhere"


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
# it has to survive being printed
# --------------------------------------------------------------------------


def test_it_carries_print_rules():
    """This ends up in a case file, which means on paper."""
    out = page_html()
    assert "@media print" in out


def test_it_is_one_document_a_browser_will_accept():
    out = page_html()
    assert out.startswith("<!doctype html>")
    assert "<html" in out and "</html>" in out
    assert 'charset="utf-8"' in out.lower()


# --------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------


def test_html_goes_to_stdout_for_a_file(capsys):
    from unmasker.cli import main

    assert main([str(BARS), "--html"]) == 1
    assert capsys.readouterr().out.startswith("<!doctype html>")


def test_html_goes_to_stdout_for_a_directory(case_folder, capsys):
    from unmasker.cli import main

    assert main([str(case_folder), "--html"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("<!doctype html>")
    assert "bids.xlsx" in out


def test_the_tool_still_writes_nothing(tmp_path, capsys):
    """`--html` prints. It does not write, because this tool never does - which
    is why it is a redirect rather than an `--out` option."""
    import shutil

    from unmasker.cli import main

    target = tmp_path / "doc.pdf"
    shutil.copy(BARS, target)
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}
    main([str(target), "--html"])
    capsys.readouterr()
    assert {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")} == before


def test_html_and_json_together_are_refused(capsys):
    """Two shapes of output down one pipe is one of them corrupted."""
    from unmasker.cli import main

    assert main([str(BARS), "--html", "--json"]) == 2
    assert "json" in capsys.readouterr().err.lower()


# --------------------------------------------------------------------------


def _text(html: str) -> str:
    """What a reader sees: tags and the stylesheet taken out."""
    body = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", body)


def _extraction(remarks=()):
    from unmasker.readers.model import Extraction, TextUnit

    return Extraction(kind="pdf", units=(TextUnit(text="something"),), remarks=remarks)
