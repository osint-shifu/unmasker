"""The screen a directory produces.

The single-file report answers *what is hidden in this document*. This one
answers *which of these do I need to open*, and the two must not be confused
for each other - a survey that printed every finding in a folder of two hundred
files would be a scroll, not a report.

So the human report triages and `--json` is the archive. That split needs no
new flag: the complete record already exists in machine-readable form, so the
screen is free to be short.
"""

from __future__ import annotations

import json
from pathlib import Path

from unmasker.report import Style
from unmasker.scan import survey
from unmasker.survey_report import render_survey
from unmasker.theme import Depth


def screen(folder, width: int = 84) -> str:
    return render_survey(survey(folder), Style(depth=Depth.NONE, width=width))


# --------------------------------------------------------------------------
# the three questions it answers
# --------------------------------------------------------------------------


def test_it_says_how_much_was_read_and_how_much_was_not(case_folder):
    text = screen(case_folder)
    assert "read" in text
    assert "refused" in text or "not read" in text


def test_it_names_every_file_that_hides_something(case_folder):
    text = screen(case_folder)
    for name in ("bids.xlsx", "minutes.pdf", "position-note.odt", "settlement.docx"):
        assert name in text


def test_it_names_the_kinds_a_file_hides_beside_it(case_folder):
    """A reader choosing what to open next needs to know whether it is stale
    metadata or a bar over a name, without opening it."""
    line = next(li for li in screen(case_folder).splitlines() if "bids.xlsx" in li)
    assert "hidden-rows" in line or "hidden-columns" in line


def test_it_names_every_file_it_could_not_read_and_why(case_folder):
    text = screen(case_folder)
    assert "attachments.zip" in text
    assert "photo.jpg" in text


def test_the_control_is_not_listed_as_hiding_anything(case_folder):
    """`clean.pdf` was redacted properly. It was read, and it belongs in
    neither the hiding list nor the refusals."""
    hiding = screen(case_folder).split("not read")[0]
    assert "clean.pdf" not in hiding


# --------------------------------------------------------------------------
# it must not rank
# --------------------------------------------------------------------------


def test_the_files_are_printed_in_path_order(case_folder):
    text = screen(case_folder)
    names = ["bids.xlsx", "minutes.pdf", "position-note.odt"]
    positions = [text.index(name) for name in names]
    assert positions == sorted(positions)


def test_the_tally_counts_files_and_says_so(case_folder):
    """`covered-text  1 file`. Not a score, not a percentage, and the noun is
    there so nobody reads the number as a count of findings."""
    text = screen(case_folder)
    assert "file" in text
    assert "%" not in text


def test_no_word_of_judgement_appears(case_folder):
    """The survey reports; it does not grade. These are the words that would
    creep in first."""
    text = screen(case_folder).lower()
    for word in ("severity", "critical", "risk", "score", "suspicious", "dangerous"):
        assert word not in text


# --------------------------------------------------------------------------
# it must not sprawl or overflow
# --------------------------------------------------------------------------


def test_nothing_runs_past_the_width(case_folder):
    for width in (60, 84, 100):
        for line in screen(case_folder, width=width).splitlines():
            assert len(line) <= width, f"{len(line)} > {width}: {line!r}"


def test_a_long_path_is_wrapped_rather_than_truncated(tmp_path):
    """`CONTRIBUTING.md`: nothing is truncated. An ellipsis in a file name is
    the one place it would cost a reader the ability to find the file."""
    deep = tmp_path / ("a" * 40) / ("b" * 40)
    deep.mkdir(parents=True)
    (deep / ("c" * 40 + ".txt")).write_text("nothing hidden here")
    text = render_survey(survey(tmp_path), Style(depth=Depth.NONE, width=60))
    assert "…" not in text and "..." not in text


# --------------------------------------------------------------------------
# an empty folder, and one where nothing could be read
# --------------------------------------------------------------------------


def test_an_empty_folder_says_there_was_nothing_to_read(tmp_path):
    text = render_survey(survey(tmp_path), Style(depth=Depth.NONE, width=84))
    assert "no files" in text.lower() or "nothing" in text.lower()


def test_a_folder_where_nothing_was_read_never_says_nothing_was_found(tmp_path):
    """The whole reason the refusals are a section. Twelve unreadable files and
    a cheerful `nothing hidden found` is the misleading report this project
    exists to avoid."""
    for name in ("a.jpg", "b.jpg"):
        (tmp_path / name).write_bytes(b"\xff\xd8\xff\xe0nope")
    text = render_survey(survey(tmp_path), Style(depth=Depth.NONE, width=84))
    assert "nothing hidden found" not in text
    assert "2" in text


# --------------------------------------------------------------------------
# --json is the archive
# --------------------------------------------------------------------------


def test_json_names_the_survey_shape_apart_from_the_scan_shape(case_folder):
    """A folder's output and a file's output are not the same document, and
    before this they announced themselves identically."""
    from unmasker.survey_report import as_json

    record = as_json(survey(case_folder))

    assert record["schema"] == "unmasker.survey/1"


def test_json_carries_every_finding_the_screen_summarised(case_folder):
    from unmasker.survey_report import as_json

    record = json.loads(json.dumps(as_json(survey(case_folder))))
    assert record["tool"] == "unmasker"
    files = {entry["file"]: entry for entry in record["files"]}
    assert len(files) == len(survey(case_folder).results)

    bids = next(v for k, v in files.items() if k.endswith("bids.xlsx"))
    assert len(bids["findings"]) > 1
    assert bids["searched"] is True


def test_json_says_which_files_were_refused_and_why(case_folder):
    from unmasker.survey_report import as_json

    record = as_json(survey(case_folder))
    refused = [f for f in record["files"] if f.get("refused")]
    # `Path(...).name`, not a split on "/": Windows spells the separator the
    # other way and the first CI run on this said so.
    assert {Path(f["file"]).name for f in refused} == {"attachments.zip", "photo.jpg"}
    assert all(isinstance(f["refused"], str) and f["refused"] for f in refused)


def test_json_never_reports_a_refused_file_as_searched(case_folder):
    from unmasker.survey_report import as_json

    for entry in as_json(survey(case_folder))["files"]:
        if entry.get("refused"):
            assert entry["searched"] is False
            assert entry["findings"] == []


# --------------------------------------------------------------------------
# the command line, given a directory
# --------------------------------------------------------------------------


def test_a_directory_is_accepted_by_the_same_command(case_folder, capsys):
    """`unmasker <path>` takes either. A reader should not have to know which
    kind of thing they are holding before they can ask about it."""
    from unmasker.cli import main

    assert main([str(case_folder)]) == 1
    assert "files that hide something" in capsys.readouterr().out


def test_a_directory_with_nothing_hidden_exits_zero(tmp_path, capsys):
    import shutil

    from conftest import SPECIMENS

    from unmasker.cli import main

    shutil.copy(SPECIMENS / "pdf" / "libreoffice-writer-properly-redacted.pdf", tmp_path)
    assert main([str(tmp_path)]) == 0
    capsys.readouterr()


def test_a_directory_where_nothing_could_be_read_does_not_exit_zero(tmp_path, capsys):
    """Exit 2 means could not be read, and that is what happened to every file
    here. Exit 0 would tell a pipeline the folder came back clean."""
    from unmasker.cli import main

    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0nope")
    assert main([str(tmp_path)]) == 2
    capsys.readouterr()


def test_ocr_is_refused_on_a_directory(case_folder, capsys):
    """Seconds a page across a case folder is hours. It says so rather than
    starting and leaving somebody to wonder."""
    from unmasker.cli import main

    assert main([str(case_folder), "--ocr"]) == 2
    assert "directory" in capsys.readouterr().err


def test_json_on_a_directory_is_the_archive(case_folder, capsys):
    from unmasker.cli import main

    assert main([str(case_folder), "--json"]) == 1
    record = json.loads(capsys.readouterr().out)
    assert "files" in record and len(record["files"]) == 8
