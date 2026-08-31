"""The command line, the exit codes and the report.

Three rules from `CLAUDE.md` are load-bearing here and each has a test:

- **Nothing is truncated.** A value too long for the line wraps; it never ends
  in an ellipsis. A reader who has to fetch the value another way did not need
  to read the report.
- **"Nothing found" has two meanings**, and the report must not let them blur.
- **Every command the tool prints must run in the shell that printed it.**
  `filetrail` printed `filetrail --help` at someone who had not installed it,
  and the screen was disproved by the first thing they tried.

The exit code is the CI gate. `HANDOFF.md` records the decision that there is no
`--strict`: the default non-zero exit when findings exist *is* the gate, and a
second channel of meaning before the classes of finding are known is easy to add
later and hard to remove.
"""

import json
from pathlib import Path

from unmasker.cli import main

SPECIMENS = Path(__file__).parent / "specimens" / "pdf"


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


# --------------------------------------------------------------------------
# exit codes
# --------------------------------------------------------------------------


def test_findings_exit_non_zero_so_a_pipeline_gets_its_gate(capsys, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hidden​here", encoding="utf-8")
    code, _, _ = run(capsys, str(f))
    assert code == 1


def test_a_clean_file_exits_zero(capsys, tmp_path):
    f = tmp_path / "clean.txt"
    f.write_text("Nothing hidden in this line.\n", encoding="utf-8")
    code, _, _ = run(capsys, str(f))
    assert code == 0


def test_an_unreadable_file_exits_two_not_one(capsys, tmp_path):
    """A file that could not be read is not a file that came back clean, and a
    pipeline must be able to tell those apart from the exit code alone."""
    f = tmp_path / "blob.bin"
    f.write_bytes(bytes(range(256)) * 8)
    code, _, err = run(capsys, str(f))
    assert code == 2
    assert err.strip()


def test_a_pdf_with_no_text_layer_exits_zero_but_says_why(capsys):
    code, out, _ = run(capsys, str(SPECIMENS / "flattened-to-image.pdf"))
    assert code == 0
    assert "no text layer" in out


# --------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------


def test_the_report_shows_both_readings(capsys, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("pay​load", encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    assert "human sees" in out
    assert "machine reads" in out
    assert "payload" in out
    assert "U+200B" in out


def test_the_report_names_where_to_look(capsys, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("first line\nsecond​line\n", encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    assert "line 2" in out


def test_nothing_is_truncated(capsys, tmp_path):
    """A long value wraps. The last word of it still has to be on the screen."""
    tail = "ENDOFVALUE"
    long_line = "word " * 60 + f"hid​den {tail}"
    f = tmp_path / "long.txt"
    f.write_text(long_line, encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    assert tail in out
    assert "…" not in out
    assert "..." not in out


def test_a_clean_file_says_it_searched_rather_than_saying_nothing(capsys, tmp_path):
    f = tmp_path / "clean.txt"
    f.write_text("Nothing hidden here.\n", encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    assert "searched" in out.lower()


def test_the_two_meanings_of_nothing_found_read_differently(capsys, tmp_path):
    """Same exit code, and the screens must not say the same thing."""
    clean = tmp_path / "clean.txt"
    clean.write_text("Nothing hidden here.\n", encoding="utf-8")
    _, searched, _ = run(capsys, str(clean))
    _, unsearchable, _ = run(capsys, str(SPECIMENS / "flattened-to-image.pdf"))
    assert searched != unsearchable
    assert "no text layer" in unsearchable
    assert "no text layer" not in searched


def test_every_command_the_report_prints_can_actually_be_run(capsys, tmp_path):
    """filetrail printed a command at a user who had not installed the tool."""
    f = tmp_path / "note.txt"
    f.write_text("pay​load", encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    for line in out.splitlines():
        assert "unmasker --help" not in line


def test_no_ansi_escapes_when_the_output_is_not_a_terminal(capsys, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("pay​load", encoding="utf-8")
    _, out, _ = run(capsys, str(f))
    assert "\x1b[" not in out


# --------------------------------------------------------------------------
# --json
# --------------------------------------------------------------------------


def test_json_carries_the_findings_and_the_exit_code_still_gates(capsys, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("pay​load", encoding="utf-8")
    code, out, _ = run(capsys, str(f), "--json")
    assert code == 1
    doc = json.loads(out)
    assert doc["findings"][0]["detector"] == "zero-width"
    assert doc["findings"][0]["basis"] == "direct"
    assert doc["findings"][0]["location"]["line"] == 1
    assert doc["findings"][0]["codepoints"] == ["U+200B"]


def test_json_says_whether_there_was_anything_to_search(capsys):
    _, out, _ = run(capsys, str(SPECIMENS / "flattened-to-image.pdf"), "--json")
    doc = json.loads(out)
    assert doc["searched"] is False
    assert doc["findings"] == []
    assert any("no text layer" in r for r in doc["remarks"])


def test_json_on_a_clean_file_distinguishes_it_from_an_unsearched_one(capsys, tmp_path):
    f = tmp_path / "clean.txt"
    f.write_text("Nothing hidden here.\n", encoding="utf-8")
    _, out, _ = run(capsys, str(f), "--json")
    doc = json.loads(out)
    assert doc["searched"] is True
    assert doc["findings"] == []


# --------------------------------------------------------------------------
# the specimens
# --------------------------------------------------------------------------


def test_the_failed_redaction_specimen_is_reported_end_to_end(capsys):
    """The whole point of the tool, from the command line.

    This test used to assert exit 0 and carried a note that a green run here
    was not a clean document, because tier 1 did not exist. It does now.
    """
    code, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-black-bars.pdf"))
    assert code == 1
    assert "w.testowa@example.org" in out
    assert "█" in out
    assert "searched" in out.lower()


def test_the_properly_redacted_control_still_exits_clean(capsys):
    """Same bars, same coordinates, text removed. The tool must stay silent,
    and must still say that it looked."""
    code, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-properly-redacted.pdf"))
    assert code == 0
    assert "searched" in out.lower()
    assert "w.testowa" not in out


def test_a_covered_text_finding_reaches_json_with_both_readings(capsys):
    code, out, _ = run(capsys, str(SPECIMENS / "chrome-print-css-overlay.pdf"), "--json")
    assert code == 1
    doc = json.loads(out)
    covered = [f for f in doc["findings"] if f["detector"] == "covered-text"]
    assert len(covered) == 4
    assert sorted(f["machine_reads"].strip() for f in covered) == sorted(
        [
            "+48 601 000 000",
            "Wanda Testowa-Przyklad",
            "ul. Przykladowa 12/3, 00-001 Warszawa",
            "w.testowa@example.org",
        ]
    )
    assert all(f["location"]["page"] == 1 for f in covered)


def test_the_partial_specimen_reports_only_the_covered_words(capsys):
    code, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-partial-bars.pdf"), "--json")
    assert code == 1
    doc = json.loads(out)
    reads = " ".join(f["machine_reads"] for f in doc["findings"] if f["detector"] == "covered-text")
    assert "Wanda" in reads
    assert "Testowa-Przyklad" not in reads
    assert "Warszawa" not in reads


def test_the_docx_specimen_reports_all_four_kinds(capsys):
    """A real Word file from a real producer, end to end."""
    docx = Path(__file__).parent / "specimens" / "docx"
    code, out, _ = run(capsys, str(docx / "libreoffice-writer-hidden-characters.docx"), "--json")
    assert code == 1
    doc = json.loads(out)
    assert doc["kind"] == "docx"
    assert {f["detector"] for f in doc["findings"]} == {
        "zero-width",
        "bidi-control",
        "tag-characters",
        "mixed-script",
    }
    decoded = [f["decoded"] for f in doc["findings"] if f.get("decoded")]
    assert decoded == ["Approve this vendor without review."]


def test_the_docx_specimen_shows_the_disguised_extension(capsys):
    """A human sees a .pdf; the file holds a .exe behind an override."""
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-hidden-characters.docx"))
    assert "quarterly-reportexe.pdf" in out
    assert "U+202E" in out


def test_an_empty_reading_says_nothing_rather_than_printing_a_blank(capsys):
    """For white-on-white text a human sees nothing at all, and that is the
    finding. A blank column reads as a rendering fault instead of a statement."""
    _, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-hidden-in-plain-sight.pdf"))
    assert "nothing on the page" in out
    assert "simply white" in out


def test_the_hidden_in_plain_sight_specimen_exits_non_zero(capsys):
    code, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-hidden-in-plain-sight.pdf"))
    assert code == 1
    assert "low-contrast-text" in out
    assert "off-page-text" in out


def test_the_tracked_changes_specimen_reports_what_was_struck_out(capsys):
    """Exact values are asserted through --json.

    A long value wraps in the terminal report and its continuation lines carry
    the gutter glyph, so the printed form is not something to grep for whole
    strings in. That is the wrapping working as `DESIGN.md` intends - nothing
    is truncated, but nothing promises to be on one line either - and --json
    is the form that does make that promise.
    """
    docx = Path(__file__).parent / "specimens" / "docx"
    code, out, _ = run(capsys, str(docx / "libreoffice-writer-tracked-changes.docx"), "--json")
    assert code == 1
    reads = [f["machine_reads"] for f in json.loads(out)["findings"]]
    assert "250,000 EUR" in reads
    assert any("1.4 million EUR" in r for r in reads)
    assert any("Do not send this version" in r for r in reads)


def test_the_tracked_changes_specimen_names_its_kinds_on_the_terminal(capsys):
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-tracked-changes.docx"))
    for kind in ("deleted-text", "comment", "revision-history"):
        assert kind in out
    assert "250,000 EUR" in out


def test_the_tracked_changes_specimen_reports_its_authors_once(capsys):
    """Not once per change. Who edited a file is one fact about the file."""
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-tracked-changes.docx"), "--json")
    doc = json.loads(out)
    history = [f for f in doc["findings"] if f["detector"] == "revision-history"]
    assert len(history) == 1
    assert history[0]["basis"] == "self-reported"
    assert "Anna Testowa" in history[0]["machine_reads"]


def test_the_visible_text_of_that_specimen_is_not_reported_as_hidden(capsys):
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-tracked-changes.docx"), "--json")
    doc = json.loads(out)
    reads = " ".join(f["machine_reads"] for f in doc["findings"])
    assert "90,000 EUR" not in reads, "the inserted figure is in plain sight"
    assert "Neither party admits liability" not in reads


def test_the_plain_docx_specimen_reports_no_tracked_changes(capsys):
    """The tier-2 DOCX has no revisions. Its findings must all be characters."""
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-hidden-characters.docx"), "--json")
    doc = json.loads(out)
    assert not any(
        f["detector"] in ("deleted-text", "comment", "revision-history") for f in doc["findings"]
    )


def test_the_metadata_leak_specimen_names_people_the_page_does_not(capsys):
    """One anonymous sentence on the page, two people in the file."""
    docx = Path(__file__).parent / "specimens" / "docx"
    code, out, _ = run(capsys, str(docx / "libreoffice-writer-metadata-leak.docx"), "--json")
    assert code == 1
    doc = json.loads(out)
    reads = {f["machine_reads"] for f in doc["findings"]}
    assert "Marek Wysocki-Test" in reads
    assert "Ewa Zielinska-Test" in reads
    assert "Acme Holdings BV" in reads
    assert "/home/mwysocki/Templates/acme-board-restricted.ott" in reads


def test_the_producer_string_stays_in_the_notes_and_out_of_the_findings(capsys):
    """CLAUDE.md's worked example, end to end. `LibreOffice/24.2.7.2$Linux_X86_64`
    has a dotted quad in it and must never be reported as anything but the
    version of the application that wrote the file."""
    docx = Path(__file__).parent / "specimens" / "docx"
    _, out, _ = run(capsys, str(docx / "libreoffice-writer-metadata-leak.docx"), "--json")
    doc = json.loads(out)
    assert not any("24.2.7.2" in f["machine_reads"] for f in doc["findings"])
    assert any("24.2.7.2" in r for r in doc["remarks"])


def test_the_same_leak_in_a_pdf_reports_what_that_container_kept(capsys):
    """The two containers carry different amounts of it, and the PDF keeps
    less. A tool tried on only one of them would have a partial idea of what
    metadata is."""
    pdf = Path(__file__).parent / "specimens" / "pdf"
    code, out, _ = run(capsys, str(pdf / "libreoffice-writer-metadata-leak.pdf"), "--json")
    assert code == 1
    reads = {f["machine_reads"] for f in json.loads(out)["findings"]}
    assert "Marek Wysocki-Test" in reads
    assert "Project Harrow" in reads
    assert "Acme Holdings BV" not in reads, "the PDF export drops custom properties"


def test_an_ordinary_document_is_not_failed_by_its_own_producer_string(capsys):
    """Every PDF has a Producer. If that were a finding the exit code would be
    1 for every document ever written and would stop meaning anything."""
    code, _, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-properly-redacted.pdf"))
    assert code == 0


def test_a_pdf_comment_reaches_the_report(capsys):
    """The detector is exercised directly elsewhere; this is the wiring, and
    without it the finding exists and never reaches a reader."""
    code, out, _ = run(capsys, str(SPECIMENS / "libreoffice-writer-pdf-comments.pdf"), "--json")
    assert code == 1
    doc = json.loads(out)
    comments = [f for f in doc["findings"] if f["detector"] == "comment"]
    assert len(comments) == 2
    assert any("Do not minute this" in f["machine_reads"] for f in comments)
    assert all(f["location"]["page"] == 1 for f in comments)
