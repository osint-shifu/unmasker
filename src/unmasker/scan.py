"""Surveying a directory instead of a file.

One file at a time is a demonstration. A case arrives as a folder, and the
question a person has then is *which of these do I need to open* - a different
question from *what is hidden in this one*, and it needs a different answer.

## Triage without ranking

`CONTRIBUTING.md` forbids ranking findings against each other, and this is
where that rule is hardest to keep: every instinct says to sort the worst files
to the top. So the survey does what the sibling project does instead - it
counts **files per kind of finding** and lists the files in path order. A
reader still learns where to look, and the tool still has not decided for them
which document matters most.

Counting *files* rather than findings is the same rule one level up. A document
with eight covered lines would otherwise make `covered-text` look eight times
more common than it is, which is a ranking wearing a tally's clothes.

## Refusals are a section, not a footnote

A folder of forty-seven files where six could not be read, reported as "twelve
files hide something", tells a reader the other thirty-five are clean. They are
not: nobody looked at six of them.

At the level of one file, *searched and found nothing* against *there was
nothing to search* is a nuance this project is careful about. At the level of a
directory it is the difference between a true report and a misleading one, so
`refused` is carried in the record beside `read` and each refusal keeps the
reason it was refused.

## What is deliberately not here

No parallelism and no progress bar. Both are answers to a measurement nobody
has taken yet, and a thread pool around a parser that will be handed hostile
files is a decision that needs its own argument.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .detect import collect
from .findings import Finding
from .readers import UnreadableFile, read


def _hidden(name: str) -> bool:
    """Whether a path component is one to walk past.

    A case folder under version control would otherwise have its whole object
    store surveyed - slow, useless, and alarming to watch. The same rule covers
    editor and OS clutter, which is what a leading dot means everywhere this
    tool runs.
    """
    return name.startswith(".")


@dataclass(frozen=True)
class FileResult:
    """One file's reading. Carries no score and no severity, on purpose:
    ranking documents against each other is the thing this project refuses to
    do, and a field here is where it would start."""

    path: Path
    kind: str | None = None
    findings: tuple[Finding, ...] = ()
    remarks: tuple[str, ...] = field(default_factory=tuple)
    searched: bool = False

    refusal: str | None = None
    """Why the file could not be read, in the reader's own words. `None` means
    it was read - which is not the same as it having nothing in it."""

    @property
    def was_read(self) -> bool:
        return self.refusal is None

    @property
    def detectors(self) -> tuple[str, ...]:
        """The kinds of finding in this file, once each, in the order the
        report will print them."""
        seen: list[str] = []
        for finding in self.findings:
            if finding.detector not in seen:
                seen.append(finding.detector)
        return tuple(seen)


@dataclass(frozen=True)
class Survey:
    root: Path
    results: tuple[FileResult, ...] = ()

    @property
    def read(self) -> tuple[FileResult, ...]:
        return tuple(r for r in self.results if r.was_read)

    @property
    def refused(self) -> tuple[FileResult, ...]:
        return tuple(r for r in self.results if not r.was_read)

    @property
    def hiding(self) -> tuple[FileResult, ...]:
        return tuple(r for r in self.results if r.findings)

    @property
    def by_detector(self) -> dict[str, int]:
        """Kind of finding -> how many **files** carry it.

        Files, not findings. A document with eight covered lines must not make
        its kind look eight times more common than it is.
        """
        tally: Counter[str] = Counter()
        for result in self.results:
            tally.update(result.detectors)
        return dict(tally.most_common())

    @property
    def findings(self) -> int:
        return sum(len(r.findings) for r in self.results)


def walk(root: Path) -> list[Path]:
    """Every file worth trying, in path order.

    Nothing is filtered by extension. Dispatch is by content everywhere else in
    this tool, and a directory walk that trusted a suffix would be the first
    place a `.txt` holding a PDF got missed.
    """
    if root.is_file():
        return [root]
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(_hidden(part) for part in path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def read_one(path: Path, ocr: bool = False) -> FileResult:
    try:
        extraction = read(path)
    except UnreadableFile as exc:
        # The reason is kept rather than reduced to a flag: a reader deciding
        # whether to go and open the file needs to know whether the tool cannot
        # read that kind of document yet, or could not read this one.
        return FileResult(path=path, refusal=str(exc))

    return FileResult(
        path=path,
        kind=extraction.kind,
        findings=tuple(collect(extraction, ocr=ocr)),
        remarks=tuple(extraction.remarks),
        searched=extraction.has_text,
    )


def survey(root: Path, ocr: bool = False) -> Survey:
    root = Path(root)
    return Survey(root=root, results=tuple(read_one(path, ocr=ocr) for path in walk(root)))
