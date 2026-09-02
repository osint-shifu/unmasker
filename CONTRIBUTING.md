# Contributing

Thank you for looking. This project has a small number of rules and every one
of them was paid for by a bug. They are worth reading before writing code,
because a change that breaks one of them will be asked to change back.

## Setting up

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

Python 3.10 or later. One runtime dependency, `pypdf`.

## The one thing this tool must never do

**State something the evidence does not support.** No "this document was
manipulated". Show what a human sees, show what a machine reads, name the gap,
and stop.

A reader who disagrees with a finding must be able to see why. A tool that
concludes for its reader is a tool whose conclusion has to be trusted blindly,
and nobody should trust this one blindly.

Everything below follows from that.

## A new detector needs a specimen a real producer wrote

This is the rule that matters most, and it is not negotiable.

A fixture built from a specification proves that your reader agrees with your
reading of the spec. It does not prove it agrees with LibreOffice. The sibling
project `filetrail` had a HEIC reader with a fully green test suite that
decoded nothing at all on every real file, because every fixture had been built
from the standard and no real encoder writes files that way.

So:

1. Write a **builder** in `tests/specimens/sources/` that drives a real
   producer — `soffice`, `google-chrome`, `gs`, `tesseract`, `exiftool` — to
   write the file.
2. Commit the produced file. The specimens **are** the test suite here, which
   is why they are in git rather than gitignored.
3. Write a `.md` beside it recording what produced it, what a human sees, what
   is actually in the file, and **what it does not carry**.

Everything in a specimen must be invented. No real documents, no real people;
the e-mail domain is `example.org`, which RFC 2606 reserves for the purpose.

If the producer does something the specification does not describe — and it
will — that is the most valuable thing in your pull request. Write it down.

## Watch the test fail first

Write the test, run it, read the failure, *then* implement. A test written
afterwards passes against broken code, and this project has caught itself
doing that twice.

Check the failure is the one you expected. An `ImportError` is not evidence
that your test works.

## Break your own rule and see whether the suite notices

Before opening a pull request, take each claim your docstrings make, break it
in the source, and run the suite. Anything that stays green is a claim nothing
is holding.

This has found something every single time it has been run here — most
recently a guard that could not fail because the fixture feeding it had a
default that made the question moot. If you find one, the fix is a test, and
that test is the interesting part of the change.

## Report a line, never a show-operation

If you are touching the PDF detectors: producers disagree wildly about how much
text one drawing operation carries. Chrome writes one glyph per `Tj`; tesseract
writes one operation per word. Group by **line on the page**, using
`detectors._lines`, or a single hidden line becomes eighty-seven findings.

That rule has been broken five times in this codebase.
`test_no_detector_reports_per_show_operation` now asks the question directly.

## Do not rank findings against each other

A page can have a bar over its text *and* invisible characters *and* stale
metadata. Those are three findings, not one winner. `filetrail` printed the
winner once, and a geotagged photograph that had been downloaded reported its
URL and no GPS at all.

Nothing here sorts by strength, and `Finding` carries no score.

## Colour and words

**Colour encodes how the tool knows, never how bad the finding is.** Three
classes — `direct`, `circumstantial`, `self-reported` — and nothing else in
the output may use colour.

Prefer a word a reader can argue with over a number that implies a precision
you do not have. `55` reads as a probability; it never was one.

## Output

- **Nothing is truncated.** A value too long for the line wraps. An ellipsis
  sends the reader to fetch the value another way.
- **Nothing draws past the width it declared.**
- A description that restates its flag teaches the reader to skip
  descriptions, and once they skip one they skip the rest.
- Every command the tool prints must run in the shell that printed it.

## Commits

Prose, and no trailers. Say what changed and **why** — the why is the part
that cannot be recovered from the diff. If a change corrects an earlier
assumption, say what the assumption was; those are the most useful messages in
this repository's history.

Stage deliberately. `git add -A` once swept a build archive into two commits of
the sibling project and it reached a public repository.

## What a good pull request looks like

- a specimen a producer wrote, with its `.md`
- a test you watched fail
- the producer fact you measured, written down where the next person will hit it
- the gap your change does *not* close, named rather than left implied

## Reporting a bug

The most useful report is a file. If it is not one you can share — and in this
line of work it usually is not — a builder that produces something with the
same shape is just as good, and better for everyone.

If a finding is wrong, say what the tool printed and what the document actually
shows. A false positive is a bug of the same size as a miss here: a report a
reader learns to scroll past has stopped working.

## Security

See [`SECURITY.md`](SECURITY.md). In short: this tool parses hostile files by
design, so a crash or a hang on a malformed document is a bug worth reporting
privately first.
