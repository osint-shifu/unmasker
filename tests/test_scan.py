"""Surveying a directory instead of a file.

One file at a time is a demonstration. A case arrives as a folder, and the
question a person actually has is *which of these do I need to open* - which
is a different question from *what is hidden in this one*, and needs a
different answer.

## Triage without ranking

`CONTRIBUTING.md` forbids ranking findings against each other, and a directory
report is where that rule is hardest to keep: every instinct says to sort the
worst files to the top. The sibling project's answer is taken wholesale
instead. Count **files per kind of finding**, list the files that hide
something in path order, and never claim one is worse than another. A reader
still knows where to look and the tool still has not judged for them.

## The section that matters most

A folder of forty-seven files where six could not be read, reported as
"twelve files hide something", tells a reader that the other thirty-five are
clean. They are not. Nobody looked at six of them.

At the level of one file, *searched and found nothing* against *there was
nothing to search* is a nuance. At the level of a directory it is the
difference between a true report and a misleading one, which is why the
refusals are a section of their own rather than a footnote.
"""

from __future__ import annotations

from unmasker.scan import survey

# --------------------------------------------------------------------------
# what it walks
# --------------------------------------------------------------------------


def test_it_walks_into_subdirectories(case_folder):
    found = {result.path.name for result in survey(case_folder).results}
    assert "settlement.docx" in found, "a nested file was not surveyed"


def test_it_never_walks_into_a_dot_directory(case_folder):
    """A case folder under version control would otherwise have its whole
    object store surveyed, which is slow, useless and alarming to watch."""
    walked = {str(result.path) for result in survey(case_folder).results}
    assert not any(".git" in path for path in walked)


def test_it_skips_dotfiles(case_folder):
    found = {result.path.name for result in survey(case_folder).results}
    assert ".hidden.pdf" not in found


def test_a_single_file_still_works(case_folder):
    """The same entry point takes either, so `unmasker <path>` does not have to
    ask what kind of thing it was given."""
    result = survey(case_folder / "minutes.pdf")
    assert len(result.results) == 1
    assert result.results[0].findings


# --------------------------------------------------------------------------
# what it counts
# --------------------------------------------------------------------------


def test_it_separates_what_was_read_from_what_was_not(case_folder):
    found = survey(case_folder)
    assert {r.path.name for r in found.refused} == {"attachments.zip", "photo.jpg"}
    assert "bids.xlsx" in {r.path.name for r in found.read}


def test_a_refusal_keeps_the_reason_it_was_refused(case_folder):
    """Two files here cannot be read for two different reasons, and a reader
    deciding whether to go and look at one needs to know which."""
    reasons = {r.path.name: r.refusal for r in survey(case_folder).refused}
    assert "zip" in reasons["attachments.zip"]
    assert reasons["photo.jpg"]
    assert reasons["attachments.zip"] != reasons["photo.jpg"]


def test_the_control_is_read_and_reported_as_hiding_nothing(case_folder):
    """`clean.pdf` was redacted properly. It must appear as read, and must not
    appear among the files that hide something."""
    found = survey(case_folder)
    assert "clean.pdf" in {r.path.name for r in found.read}
    assert "clean.pdf" not in {r.path.name for r in found.hiding}


def test_files_that_hide_something_are_listed(case_folder):
    hiding = {r.path.name for r in survey(case_folder).hiding}
    assert {
        "bids.xlsx",
        "deck.pptx",
        "minutes.pdf",
        "position-note.odt",
        "settlement.docx",
    } <= hiding


# --------------------------------------------------------------------------
# triage without ranking
# --------------------------------------------------------------------------


def test_it_counts_files_per_kind_of_finding(case_folder):
    """Not findings, and not a score. `covered-text 1 file` answers *where do
    I look* without claiming that file is worse than any other."""
    kinds = survey(case_folder).by_detector
    assert kinds["covered-text"] == 1
    assert kinds["hidden-rows"] == 1
    assert kinds["deleted-text"] >= 1


def test_a_file_with_two_findings_of_one_kind_counts_once(case_folder):
    """The count is files, so a document with eight covered lines does not
    make its kind look eight times more common than it is."""
    found = survey(case_folder)
    minutes = next(r for r in found.results if r.path.name == "minutes.pdf")
    assert len([f for f in minutes.findings if f.detector == "covered-text"]) > 1
    assert found.by_detector["covered-text"] == 1


def test_the_files_are_in_path_order_and_not_ranked(case_folder):
    """Sorting by how much a file hides is the ranking this project forbids,
    and it is the first thing anybody would reach for here."""
    names = [str(r.path) for r in survey(case_folder).hiding]
    assert names == sorted(names)


def test_nothing_carries_a_score():
    from unmasker.scan import FileResult

    assert not any(field in FileResult.__dataclass_fields__ for field in ("score", "severity"))


# --------------------------------------------------------------------------
# an empty folder, and a folder of nothing readable
# --------------------------------------------------------------------------


def test_an_empty_directory_says_so_rather_than_reporting_clean(tmp_path):
    found = survey(tmp_path)
    assert found.results == ()
    assert not found.read


def test_a_directory_where_nothing_could_be_read_is_not_a_clean_directory(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0nope")
    (tmp_path / "b.jpg").write_bytes(b"\xff\xd8\xff\xe0nope")
    found = survey(tmp_path)
    assert not found.read
    assert len(found.refused) == 2
    assert not found.hiding
