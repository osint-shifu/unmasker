"""Hidden slides and speaker notes, and what to report about them.

A deck conceals two ways no other container does.

A **slide marked hidden** is skipped when the deck is shown and travels with
the file exactly as it was authored - the slide that was cut before the meeting
and never deleted.

A **speaker note** was never on the screen at all. That is what notes are for,
and it is why people write candid things in them, and why the candid thing goes
out with the file.

Both are the same statement this tool makes everywhere: in the file, not on the
thing anybody looked at. So the record and the findings live here and each
format contributes only a reader - the arrangement `revisions.py` and
`sheets.py` already use.

## Three rules, and one of them was a decision

**A hidden slide is one finding, quoting everything on it.** Not one per text
frame: a slide is what a person recognises, and the producers disagree about
how many frames a slide has anyway.

**Notes on a hidden slide are not reported separately.** The slide is already
the finding, and saying its notes are also unseen tells a reader nothing they
did not just read - the same rule that keeps a hidden sheet from also reporting
its hidden rows.

**Speaker notes are a finding, not a remark.** This one was a judgement. A note
is a designed, labelled part of the format and every deck has the field; it
would have been defensible to remark on them instead. They are reported because
a note is content in the file that is not on the thing an audience saw, which
is the definition this whole tool runs on - and because unlike a `Producer`
string, an *empty* notes field is the common case, so this does not fire on
every deck ever written.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .findings import Basis, Finding, Location


@dataclass(frozen=True)
class Slide:
    number: int
    """1-based, and it is the number the person who hid it saw."""

    text: str = ""
    """What is drawn on the slide, frames joined in document order."""

    notes: str = ""
    """The speaker's own copy. Never on the screen, by design."""

    hidden: bool = False
    title: str | None = None


@dataclass(frozen=True)
class SlideRecord:
    slides: tuple[Slide, ...] = ()
    remarks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def visible_text(self) -> str:
        """What an audience read, one slide per block.

        The hidden slides and every note are left out, which is the whole
        reason a deck needs its own reader: yielding all of it would hand the
        concealed half to the character detectors as though somebody had seen
        it, and then report the deck clean.
        """
        return "\n".join(s.text for s in self.slides if not s.hidden and s.text.strip())


def _count(text: str) -> str:
    return f"{len(text)} character" + ("" if len(text) == 1 else "s")


def hidden_slides(record: SlideRecord) -> list[Finding]:
    findings = []
    for slide in record.slides:
        if not slide.hidden:
            continue
        # Notes belong to the slide, so a hidden slide's notes are hidden with
        # it and quoted here rather than reported twice.
        carried = "  ".join(part for part in (slide.text, slide.notes) if part.strip())
        if not carried.strip():
            continue
        named = f' ("{slide.title}")' if slide.title else ""
        findings.append(
            Finding(
                detector="hidden-slide",
                basis=Basis.DIRECT,
                summary=(
                    f"slide {slide.number}{named} is marked hidden, so it is "
                    f"skipped when the deck is shown; {_count(carried)} of it "
                    "are still in the file"
                ),
                human_sees="",
                machine_reads=carried,
                location=Location(),
            )
        )
    return findings


def speaker_notes(record: SlideRecord) -> list[Finding]:
    findings = []
    for slide in record.slides:
        if slide.hidden or not slide.notes.strip():
            continue
        findings.append(
            Finding(
                detector="speaker-notes",
                basis=Basis.DIRECT,
                summary=(
                    f"slide {slide.number} carries a speaker note, which is in "
                    "the file and was never on the screen"
                ),
                human_sees="",
                machine_reads=slide.notes,
                location=Location(),
            )
        )
    return findings


def detect(record: SlideRecord) -> list[Finding]:
    """Every presentation finding in one deck. Additive, and neither outranks
    the other."""
    return hidden_slides(record) + speaker_notes(record)
