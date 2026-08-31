# chrome-transparent-text.pdf

Two of the four paragraphs cannot be read from the page. Nothing is drawn over
them, no render mode is changed, and their colour is plain black: they are
simply painted at no opacity.

- 19 387 bytes, `sha256:b87e9e193afdff23…`
- `/Producer` `Skia/PDF m152`, `/Creator` `HeadlessChrome/152.0.0.0`

## How it was made

```bash
python3 tests/specimens/sources/build_chrome_transparent_text.py \
    tests/specimens/pdf/chrome-transparent-text.pdf
```

An HTML page with `color: transparent` on one paragraph and `opacity: 0.1` on
another, printed by headless Chrome. One CSS declaration each.

## What a human sees

```text
BIDDING NOTE - SYNTHETIC

This paragraph is ordinary black text and must not be reported.


Three paragraphs above. Only two of them can be read from the page.
```

A blank gap, and — depending on the screen — a ghost of a line at the bottom.

## What is actually in the file

| line | how it is hidden | what a parser reads |
| --- | --- | --- |
| 3 | `/ca 0` | `The reserve price is 4.2 million and we will go to 5 if pushed.` |
| 4 | a transparency group at `/ca 0.1` | `This line is set at one tenth opacity and is very nearly not there.` |

## Why this specimen exists

It was not on the gap list. It turned up while looking for a producer that
would emit render mode 3, and what it produced instead was a hole in the tool.

**Chrome does not use `3 Tr` for transparent text.** It sets `/ca 0` in an
`ExtGState` and paints normally. So:

- a detector reading only `Tr` finds nothing here
- a detector reading only colour finds black text on white paper and calls it
  perfectly legible
- and `unmasker` reported nothing at all about this file until `TextRun` was
  given the alpha it was painted with

## The part that is not obvious

`opacity: 0.1` does not set an alpha on the text. Chrome renders the paragraph
into a **transparency group** — a Form XObject with
`/Group << /S /Transparency >>` — painted with `/ca 0.1`, and the text *inside*
the group is fully opaque.

That is how the format works: a group is composited into its parent using the
alpha in force when it was painted, and inside it the alpha starts again at 1.
Reading only the inner alpha calls the text visible; carrying the outer alpha
in unchanged applies it twice, and 0.1 squared is below the threshold that
means *paints nothing at all*. Both mistakes are covered by tests, because
neither shows up on this file — Chrome re-declares `/ca 1` inside the group, so
the double-application is invisible here and only a synthetic page catches it.

## The two readings

The empty line is `direct`: at zero opacity nothing is on the page, and there
is nothing to argue about. The tenth-opacity line is `circumstantial`: it may
still be legible on a good screen, and one tenth is also how a watermark is
set. The measured opacity is in the summary either way.
