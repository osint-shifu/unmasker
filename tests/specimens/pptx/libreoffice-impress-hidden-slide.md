# libreoffice-impress-hidden-slide.pptx

A board review with a slide that was cut and a note the speaker was told not to
say out loud. Neither is on the screen and both travel with the file.

- 15 213 bytes
- produced by LibreOffice 24.2 Impress

Its sibling [`odp/libreoffice-impress-hidden-slide.odp`](../odp/libreoffice-impress-hidden-slide.md)
is the same deck in the other family, which states the hiding completely
differently.

## How it was made

```bash
python3 tests/specimens/sources/build_impress_deck.py \
    tests/specimens/odp/libreoffice-impress-hidden-slide.odp \
    tests/specimens/pptx/libreoffice-impress-hidden-slide.pptx
```

## What a human sees

Three slides in the file, two of them shown:

```text
Q3 board review
Revenue held. Two contracts renewed on the same terms.

Outlook
Guidance unchanged.
```

## What is actually in the file

| | | |
| --- | --- | --- |
| `<p:sld show="0">` on slide 2 | the cut slide | `Redundancies - draft`, `41 roles, mostly Warsaw. Announce after the results, not before.` |
| `ppt/notesSlides/notesSlide1.xml` | slide 1's note | `Do not give the headcount number if anyone asks. Legal has not signed it off.` |

## What it is for

**This specimen was blocked for most of the project's life**, and that is the
most useful thing about it.

`unmasker` refused decks outright and said so, rather than half-reading one.
Reading a deck as a text document would have reported a hidden slide and a
speaker note as ordinary visible prose and then called the file clean — the
same defect the spreadsheet reader was written to remove.

The reader could not be written honestly, because `libreoffice-impress` was
not installed: no producer on this machine could write a deck, and
`CONTRIBUTING.md` is explicit that a detector proved only against a hand-built
fixture is the shape of the bug that started this project. Installing Impress
is the whole of what unblocked it. The refusal was the right answer for as
long as that was true.

**The producer fact, measured.** `show="0"` is written on a hidden slide and
**omitted entirely** on a shown one.

That is the opposite of what the same producer does for a hidden *row* in a
spreadsheet, where it writes `hidden="false"` out loud on every row — a fact
this project had already measured and written down. A reader carrying that
habit across, testing what the attribute *says* rather than whether it is
there, would find no hidden slides at all. Two containers, one producer,
opposite conventions.

**Order comes from the deck, not the part names.** `ppt/slides/slide10.xml`
sorts before `slide2.xml`, so the slide numbers are taken from `sldIdLst` in
`ppt/presentation.xml`. A renumbered deck sends a reader to the wrong slide,
which is worse than not numbering them at all.

**A notes slide repeats the slide's own text.** PresentationML puts a copy of
the slide's title into a placeholder on the notes slide, so reading every
`a:t` in the part quotes the slide back as though the speaker had written it.
Only the body placeholder is taken.

## What this specimen does not carry

- **PowerPoint itself.** Not on this machine. LibreOffice writes valid
  PresentationML, but two producers never agree about everything — the PDF
  specimens proved that twice and the spreadsheet specimens twice more.
- **A comment.** PowerPoint stores them in `ppt/comments/`, and LibreOffice
  writes none.
- **Text placed outside the slide**, which is the presentation's version of
  `off-page-text` and needs slide dimensions to judge.
- **A hidden slide that also carries a note**, which is reported as one
  finding rather than two; only a synthetic test exercises it.
