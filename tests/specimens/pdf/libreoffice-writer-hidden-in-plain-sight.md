# libreoffice-writer-hidden-in-plain-sight.pdf

Nothing is drawn over anything. Three lines are hidden by being painted in the
colour of what is behind them, or by being positioned where no viewer looks —
and one line is ordinary black text that must stay unreported.

- 18 419 bytes, `sha256:3839a156d371dfe3…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`, cropped afterwards with
  pypdf

## How it was made

```bash
python3 tests/specimens/sources/build_libreoffice_hidden_in_plain_sight.py \
    tests/specimens/pdf/libreoffice-writer-hidden-in-plain-sight.pdf
```

Three passes. The first exports the text alone so poppler can measure where the
coloured line lands; the second re-exports with a box of the same colour drawn
**behind** it (`style:run-through="background"`); the third raises the CropBox
above the last line.

The box is placed on `pdftotext -bbox` measurements rather than this project's
own, for the reason `libreoffice-writer-partial-bars.md` sets out: a fixture
measured with the tool under test proves only that the tool agrees with itself.

## What a human sees

```text
HIDDEN IN PLAIN SIGHT - SYNTHETIC

This line is ordinary black text and must not be reported.

███████████████████████████████████████████

Every line above is in the file. Two of them are painted in a colour that
hides them, and a fourth lies below the crop box.
```

One heading, one readable line, a solid navy bar with nothing legible on it, a
blank gap where a sentence should be, and no sign at all of the fourth line.

## What is actually in the file

| line | how it is hidden | what a parser reads |
| --- | --- | --- |
| 3 | `#ffffff` on the bare page | `Nothing is drawn over this line; it is simply white.` |
| 4 | `#1a3a5f` on a `#1a3a5f` box drawn behind it | `This line is the colour of the box it sits on.` |
| 6 | below the CropBox | `This line lies below the crop box and no viewer will show it.` |

Poppler confirms the crop independently: `pdfinfo` reports the page as
595.304 × 741.89 pt while `pdftotext` still returns the hidden line. The
MediaBox is 841.89 pt tall; the CropBox starts at y=100.

## The detour worth recording

The third line was meant to sit outside the page entirely. It cannot be made
that way with this producer: **LibreOffice will not emit content that lies
outside the paper.** A frame at `svg:x="-9.5cm"` is clamped back onto the page;
frames at `24cm` and `30cm` are dropped from the output altogether. Both were
tried.

So the specimen uses the technique that is both achievable and more common in
the wild: a CropBox smaller than the MediaBox. That is how a PDF is trimmed
without anything being removed — every viewer honours it, no parser does — and
it is why "cropped" files keep turning out to contain what was cropped off.

pypdf applies the crop, which is an ordinary thing for a PDF tool to do. It is
worth being explicit that this is the one specimen not produced end to end by a
separate application; the crop is a single dictionary entry, not geometry this
project computed.

## What it is for

Every detector that works by looking for something drawn *over* text must stay
silent here, and `covered_text` and `invisible_text` are asserted to find
nothing on it. A tool that reported this file for the wrong reason would have
found the right document by accident.
