"""The README's example output has to be output the tool actually produced.

Every other invariant on the front page is already checked - the detector
table, the detector badge, the specimen count, the test count - because a
README drifts silently and nobody notices until a reader runs the command and
gets something else.

The example blocks are the same class of thing and were the last part still
maintained by hand. They had already drifted: one block claimed four findings
and listed two, another showed two findings for a file that produces seven.

So: a ```bash block holding a single `unmasker <path>` command, immediately
followed by a ```text or ```json block, is a claim that the second is what
the first prints. This runs it and compares.

The JSON block carries the version and the schema string, so it goes stale on
its own the first time either moves. That is worth a failing test at exactly
the moment somebody bumps the version and not a release later.

The width is fixed here rather than in the README, because `--width` is not
something a reader would type - their terminal decides it. 74 is the widest
that still pushes the longest specimen path onto its own line: one column more
and the header runs the path straight into the count beside it, which on
GitHub reads as though the count were part of the file name.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

import pytest

from unmasker.cli import main

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

WIDTH = 74

#: How many command/output pairs the README is expected to carry. Asserted so
#: that renaming a fence, or deleting a block, fails loudly instead of leaving
#: a test that checks nothing and still passes.
EXPECTED_PAIRS = 5

_FENCE = re.compile(r"^```(\w*)\s*$")


class _Utf8(io.StringIO):
    """A stream that captures text and admits it can encode the box drawing.

    `glyphs()` asks the stream for its encoding and falls back to ASCII when
    there is none. A bare StringIO has no `encoding`, so capturing with one
    would compare the README against the ASCII fallback and quietly accept a
    report nobody sees.
    """

    encoding = "utf-8"


def _blocks(text: str) -> list[tuple[str, str]]:
    """Every fenced block, as (language, body)."""
    out: list[tuple[str, str]] = []
    language: str | None = None
    body: list[str] = []

    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence and language is None:
            language, body = fence.group(1), []
        elif fence:
            out.append((language or "", "\n".join(body)))
            language = None
        elif language is not None:
            body.append(line)

    return out


def _pairs(text: str) -> list[tuple[str, str]]:
    """Each `unmasker <path>` command followed directly by an output block."""
    blocks = _blocks(text)
    found = []

    # Pairwise, so the two sequences differ by one on purpose.
    for (language, body), (next_language, output) in zip(
        blocks, blocks[1:], strict=False
    ):
        command = body.strip()
        if language != "bash" or next_language not in ("text", "json"):
            continue
        if not command.startswith("unmasker ") or "\n" in command:
            continue
        # A command with a redirect or a pipe is teaching shell plumbing, not
        # showing output, and running it would write to the checkout.
        if any(character in command for character in ">|&"):
            continue
        found.append((command, output))

    return found


def _as_written(text: str, argv: list[str]) -> str:
    """Spell the paths the command was given the way the README spells them.

    `file` is parsed as a Path, so Windows renders `tests/specimens/x.pdf`
    back as `tests\\specimens\\x.pdf` - and inside `--json`, with the
    separator escaped again. The README is written once, in the spelling most
    of its readers will type.

    Skipping the comparison on Windows instead would leave three of the nine
    CI jobs checking nothing, which is how a separator cost this repository
    those same three jobs once already.
    """
    for argument in argv:
        native = str(Path(argument))
        if native == argument:
            continue
        # The escaped form first: it contains the plain one.
        text = text.replace(json.dumps(native)[1:-1], argument)
        text = text.replace(native, argument)

    return text


def _run(command: str) -> str:
    """Run the command the README shows, and return what it printed."""
    stream = _Utf8()
    argv = command.split()[1:]
    if "--json" not in argv:
        argv += ["--width", str(WIDTH)]

    with contextlib.redirect_stdout(stream):
        main(argv)

    return _as_written(stream.getvalue(), argv)


README_PAIRS = _pairs(README.read_text(encoding="utf-8"))


def test_the_readme_still_carries_its_examples() -> None:
    """A renamed fence would otherwise leave every check below vacuous."""
    assert len(README_PAIRS) == EXPECTED_PAIRS, [c for c, _ in README_PAIRS]


@pytest.mark.parametrize(
    ("command", "shown"), README_PAIRS, ids=[" ".join(c.split()[1:]) for c, _ in README_PAIRS]
)
def test_the_readme_shows_what_the_command_prints(
    command: str, shown: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    # Only blank lines at the very edges are normalised. A report opens
    # with one for breathing room under the shell prompt, which a fenced
    # block has no use for.
    assert _run(command).strip("\n") == shown.strip("\n")
