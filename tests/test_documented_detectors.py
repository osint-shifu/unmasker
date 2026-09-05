"""`README.md` is held against the detectors, so it cannot quietly go stale.

`about.py` argues that a count belongs "in the README beside the list it
counts", and that reasoning was right. It was also not enough: the README then
said **22 detectors** while the source emitted 25, and said **439 tests** while
the suite collected 706. Putting a number next to a list does not keep the
number true. Only something that fails when they disagree does.

So the tables are parsed. Every slug the source can emit has to appear in a
detector table, every slug in a table has to be one the source actually emits,
and the badge has to agree with both. Any of the three failing is a red test
rather than a wrong front door.

The two other counts the README states - specimens and tests - are held the
same way, at the bottom of this file.

## What counts as a detector, to a parser

A slug reaches a report in one of two ways, and both are a parameter named
`detector`: as `Finding(detector="zero-width", ...)` written out, or handed to
a helper that builds a family of them - `_under(page, ("fill",),
"covered-text")` in `pdf/detectors.py`, `_axis(record, "hidden-rows", ...)` in
`sheets.py`. Reading only the keyword form finds 20 of the 25 and calls the
document complete, which is the same shape of green-and-wrong the specimens
exist to prevent.

So this resolves the parameter by name in either position. A helper that grows
a `detector` argument is picked up with no change here; one that names the
parameter something else is not, and that is the known edge - it is why the
count is asserted as well as the set, because a slug that goes missing from
both sides at once still moves the total.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SOURCE = ROOT / "src" / "unmasker"

#: The header row that marks a detector table. Anything else in the file is
#: prose or another kind of table and is left alone. Named columns rather than
#: `| | |`, which renders an empty header row on GitHub and gives a parser
#: nothing to key on.
DETECTOR_HEADER = ("detector", "what it reports")

#: `![... 25 detectors ...](...detectors-25-...)` in the badge line.
_BADGE = re.compile(r"badge/detectors-(\d+)-")

#: "There are 31 of them and they are the test suite" and "713 tests."
_SPECIMENS = re.compile(r"There are (\d+) of them")
_TESTS = re.compile(r"^(\d+) tests\.$", re.MULTILINE)

SPECIMENS = ROOT / "tests" / "specimens"

#: The first cell of a detector row is the slug and nothing else. The
#: trailing hyphens are optional: `comment` is a detector and an earlier
#: version of this pattern required one, so it read 24 of the 25 and
#: blamed the README for the one it could not see.
_SLUG = re.compile(r"^`([a-z][a-z0-9]*(?:-[a-z0-9]+)*)`$")


def _rows(header: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every row under every table whose header row matches."""
    found: list[tuple[str, ...]] = []
    inside = False
    for line in README.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            inside = False
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if tuple(cell.lower() for cell in cells) == header:
            inside = True
            continue
        if inside and set("".join(cells)) <= set(":- "):
            continue  # the separator under the header
        if inside:
            found.append(cells)
    return found


def _documented() -> set[str]:
    """Every detector slug the README's tables name."""
    out = set()
    for row in _rows(DETECTOR_HEADER):
        match = _SLUG.match(row[0])
        if match:
            out.add(match.group(1))
    return out


def _emitted() -> set[str]:
    """Every slug the source can put in a `Finding`.

    Resolved through the parameter name rather than the call shape, so the
    helpers in `pdf/detectors.py` and `sheets.py` are read the same way as a
    `Finding` built in place.
    """
    found: set[str] = set()
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        # Which argument position each function in this module calls `detector`.
        position: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                arguments = node.args.posonlyargs + node.args.args
                for index, argument in enumerate(arguments):
                    if argument.arg == "detector":
                        position[node.name] = index

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "detector" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        found.add(keyword.value.value)
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            index = position.get(name)
            if index is not None and index < len(node.args):
                argument = node.args[index]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    found.add(argument.value)
    return found


# --- the tables are there at all ---------------------------------------------


def test_the_detector_tables_are_found():
    """A header nobody can parse would make every check below vacuous."""
    assert _rows(DETECTOR_HEADER), f"no table headed {DETECTOR_HEADER} in {README.name}"


def test_the_source_emits_detectors_at_all():
    """The same guard from the other side: an extractor that silently returns
    nothing would agree with an empty README forever."""
    assert _emitted(), "no detector slugs found in the source at all"


# --- and they say what the code does -----------------------------------------


def test_every_detector_the_source_emits_is_documented():
    missing = _emitted() - _documented()

    assert not missing, f"emitted but undocumented: {sorted(missing)}"


def test_nothing_is_documented_that_the_source_never_emits():
    """A promise the tool does not keep is worse than a gap in the table."""
    invented = _documented() - _emitted()

    assert not invented, f"documented but never emitted: {sorted(invented)}"


def test_the_badge_counts_what_the_tables_list():
    """The claim on the front door, against the list behind it.

    This is the one that actually drifted: the tables were right and the badge
    said 22.
    """
    claimed = _BADGE.search(README.read_text(encoding="utf-8"))

    assert claimed, "no detector-count badge found in README.md"
    assert int(claimed.group(1)) == len(_documented()) == len(_emitted())


# --- the other two numbers on the same page ----------------------------------


def _specimen_files() -> set[Path]:
    """The committed specimens themselves.

    Not the `.md` beside each one, which is its provenance note rather than a
    specimen, and not `sources/`, which holds the builders that drive the real
    producers.
    """
    return {
        path
        for path in SPECIMENS.rglob("*")
        if path.is_file()
        and path.suffix != ".md"
        and "sources" not in path.relative_to(SPECIMENS).parts
    }


def test_the_specimen_count_is_the_number_of_specimens():
    claimed = _SPECIMENS.search(README.read_text(encoding="utf-8"))

    assert claimed, "README no longer states how many specimens there are"
    assert int(claimed.group(1)) == len(_specimen_files())


def test_the_test_count_is_the_number_of_tests(request):
    """Asserted against what this run actually collected.

    Only on a whole-suite run: `pytest tests/test_sheets.py` collects a subset
    by design, and a check that called that a stale README would be a check
    nobody could run.
    """
    arguments = request.session.config.args
    whole_suite = [Path(a).resolve() for a in arguments] == [ROOT / "tests"]
    if not whole_suite:
        import pytest

        pytest.skip(f"subset run: {arguments}")

    claimed = _TESTS.search(README.read_text(encoding="utf-8"))

    assert claimed, "README no longer states how many tests there are"
    assert int(claimed.group(1)) == request.session.testscollected
