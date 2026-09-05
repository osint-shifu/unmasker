# `libreoffice-writer-word97-marks.doc`

**Producer:** LibreOffice 24.2 Writer, exported to Word 97. Built by
[`sources/build_legacy_word_marks.py`](../sources/build_legacy_word_marks.py).

## What a person sees

Three short paragraphs:

> Award notice.
> Both bids were compliant.
> Panel decision  is final.

## What is stored inside

Two more things, in the same piece table, indistinguishable from the printed
text by anything in the characters themselves:

| | |
| :--- | :--- |
| a tracked deletion | *The second bidder was disqualified for a late submission.* |
| a run marked hidden | *- reserve bidder is Wykonawca B -* |

**This is the file that proves a piece-table reader is not enough.** A .doc
keeps deleted text beside the text that is printed, and text carrying Word's
hidden attribute the same way. A reader that walks the piece table and stops
hands both on as text a person can see — reporting a deleted sentence as
though it were on the page, and reporting hidden text as ordinary prose, which
is the exact statement this tool exists to contradict.

Which characters those are lives in a `Chpx`: a short property list, in a
512-byte page, reached through `PlcfBteChpx`, and addressed **by byte offset
into the stream** while everything else counts characters.

## What came out of these bytes rather than out of a specification

The sprm numbers, and one of them corrected a wrong memory:

| sprm | | on |
| :--- | :--- | :--- |
| `0x0800` | deleted by a revision mark | the disqualification sentence |
| `0x0801` | inserted by a revision mark | *Both bids were compliant.* |
| `0x083C` | hidden | *- reserve bidder is Wykonawca B -* |
| `0x4863` / `0x4804` | who, as an index | 1 and 2 |
| `0x6864` / `0x6805` | when, as a `DTTM` | 2019-04-02 11:14, 2019-04-03 09:00 |

`0x0800` is the **delete** mark and `0x0801` the insert, not the other way
round. Guessing that pair backwards produces a tool that takes insertions off
the page *and* reports deletions as visible text — wrong in both directions at
once, and green against any fixture built from the same wrong memory.

`SttbfRMark`, which holds the names, is an extended string table with a
`0xFFFF` header. `GrpXstAtnOwners`, which holds the comment authors, is a bare
run of counted strings with no header at all. Two string tables, two layouts,
one stream — and reading the second as though it were the first eats the first
two characters of the first name, which is what happened here before the bytes
were dumped.

The `DTTM` layout was worked out against these two known dates rather than
recalled, and the reader returns `None` where the fields do not make a date. A
wrong timestamp in a forensic report is worse than an absent one: somebody
would act on it.

## What this specimen does not cover

A **moved** range, which Word records as a paired deletion and insertion with
a bookmark tying them together. This reader reports the two halves.

Everything in the metadata and the text is invented.
