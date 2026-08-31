# libreoffice-writer-tracked-changes.docx

A draft settlement note with two tracked deletions, one tracked insertion and a
comment. Nothing is drawn over anything and no character is invisible: the
hiding is done entirely by the application agreeing not to display part of its
own file.

- 5 977 bytes, `sha256:072bdd9fe0db1dd7…`
- produced by LibreOffice 24.2 Writer

## How it was made

```bash
python3 tests/specimens/sources/build_docx_tracked_changes.py \
    tests/specimens/docx/libreoffice-writer-tracked-changes.docx
```

Flat ODF with a `<text:tracked-changes>` block, converted with `soffice
--convert-to docx`. Checked before it was committed: `w:del`, `w:ins`,
`w:delText`, `w:author` and `w:date` all survive the ODF-to-OOXML conversion,
and an ODF annotation becomes `word/comments.xml`.

A settlement note because that is where this failure actually costs something.
The figure that was struck out and the sentence that was deleted are exactly
what the other side is not supposed to have, and the comment says so out loud.

## What a human sees

With the review pane showing the final text — which is how a document arrives
after someone has "accepted" their own edits by simply not displaying them:

```text
DRAFT SETTLEMENT NOTE - SYNTHETIC

This note records the position reached at the meeting of 17 April 2024.

The parties agree to settle for 90,000 EUR, payable within thirty days.

Neither party admits liability by signing it.
```

## What is actually in the file

| | | |
| --- | --- | --- |
| `w:del` | Anna Testowa, 2024-04-17T10:22:00Z | `250,000 EUR` |
| `w:del` | Piotr Przyklad, 2024-04-18T09:05:00Z | `The claimant's own expert put the exposure at 1.4 million EUR.` |
| `w:ins` | Anna Testowa, 2024-04-17T10:23:00Z | `90,000 EUR` |
| comment | Anna Testowa, 2024-04-19T11:00:00Z | `Do not send this version to the other side - the earlier figure is still in the file.` |

The first figure is nearly three times the second. The deleted sentence gives
the claimant's own valuation. Neither is on the page.

## What it is for

Three things, and the split between them is the point.

**The two deletions must be reported**, with their authors and dates. Text off
the page and still in the file is this tool's whole subject, and here it
arrives with no geometry involved at all.

**The insertion must not be reported as hidden text.** `90,000 EUR` is in the
final document, in plain sight. A detector that reported it would be calling
the visible document a concealment.

**The authors must be reported once.** Who edited a file and when is one fact
about the file, not one fact per change; a real draft carries hundreds of
revisions and a finding per revision is a report nobody finishes. It is
`self-reported`, which is what that evidence class exists for — a name in a
.docx is whatever that copy of Word was configured to say, and the report says
so rather than treating it as identification.

The deleted sentence contains an apostrophe, which OOXML writes as `&apos;`.
A test asserts it comes back as an apostrophe: reporting the entity would be
reporting the encoding rather than the text.

## What this specimen does not carry

- **`w:moveFrom` / `w:moveTo`.** The reader handles them and a synthetic test
  covers them, but LibreOffice does not emit move tracking, so nothing here
  exercises them against a real producer.
- **A deleted paragraph mark**, which merges two paragraphs and quotes nothing.
  Covered synthetically, not by a producer.
- **Formatting changes** (`w:rPrChange`). Deliberately: they carry an author and
  no hidden text, so the tool remarks on them and reports nothing.
- **Word itself.** Word is not on this machine. LibreOffice writes valid OOXML
  revision markup, but the two do not agree about everything, and this is the
  same producer-coverage gap the PDF specimens have.
