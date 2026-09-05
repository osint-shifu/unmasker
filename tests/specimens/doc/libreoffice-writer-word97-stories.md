# `libreoffice-writer-word97-stories.doc`

**Producer:** LibreOffice 24.2 Writer, exported to Word 97. Built by
[`sources/build_legacy_word_stories.py`](../sources/build_legacy_word_stories.py).

## What a person sees

An award notice: three paragraphs, a two-row table of scores, a header, a
footer, a footnote and a text box. One sentence links to a *published summary*.

## What is stored inside

**Less than half of this document's text is in the part a reader would call
the document.**

| Story | Characters | |
| :--- | ---: | :--- |
| `ccpText` | 267 | the paragraphs and the table |
| `ccpFtn` | 56 | the footnote |
| `ccpHdd` | 88 | the header and the footer |
| `ccpAtn` | 54 | a comment |
| `ccpTxbx` | 38 | the text box |
| | **504** | including one trailing paragraph mark |

A .doc lays all of it end to end in a single character-position space and the
FIB says how long each part is. A reader that took `[0, ccpText)` and stopped
would search 53% of this file and then report that it had searched it — and
the part it skipped is the part worth reading: a comment saying *we should not
name the second bidder here*, a header marked *internal circulation only*, a
footnote recording a withdrawal, a text box saying the figures are not
approved.

That is `filetrail`'s HEIC failure arriving in a new format. Its reader took
the first `Exif\0\0` in the file, which the specification does describe, and
decoded nothing from any real HEIC while its suite stayed green.

## Three things a specification reader would not have built

**The hyperlink is a field.** The bytes hold

```
0x13  HYPERLINK "https://internal.example.invalid/tender/2019/final-scores"  0x01 0x14
published summary  0x15
```

an instruction, a separator and a result. The page shows *published summary*;
the URL is on no page at all. Concatenating the run would put that URL into
the visible text, and every detector downstream would then be comparing
metadata against a page nobody can see.

**The table is not tab-separated.** A cell ends with `0x07` and so does the
row after it.

**The text is UTF-16, not the compressed 8-bit form**, though every character
in the main paragraph is ASCII. The specification presents the 8-bit piece
first; LibreOffice never writes one, so a reader built in the order the
specification reads gets the rare case tested and the common one guessed at.

## What this specimen does not cover

Tracked changes and hidden text — those are
[`libreoffice-writer-word97-marks.doc`](libreoffice-writer-word97-marks.doc).

A comment **date**. The 30-byte `ATRD` LibreOffice writes carries the owner's
index and their initials and nothing else, so the report says the file states
no date rather than guessing one.

Everything in the metadata and the text is invented.
