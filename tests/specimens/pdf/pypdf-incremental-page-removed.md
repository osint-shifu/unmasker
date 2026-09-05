# `pypdf-incremental-page-removed.pdf`

**Producers:** LibreOffice 24.2 Writer for the document, pypdf 6.16 for the
incremental delete. Built by
[`sources/build_incremental_update.py`](../sources/build_incremental_update.py).

## What a person sees

One page. An award notice saying the contract has been awarded and the file is
closed. No figure, no name.

## What is stored inside

Two revisions, one after the other, in 12 637 bytes:

| Revision | Ends at byte | Pages | Holds |
| :--- | ---: | ---: | :--- |
| 1 | 12 298 | 2 | `ANNEX A. Reserve price 240000 EUR. Kowalski told before bids closed.` |
| 2 (current) | 12 637 | 1 | the notice only |

The annex was not removed. A PDF is **appended to**, never rewritten: the
original bytes stay where they are and a new cross-reference section is written
after them. Revision 2's catalogue stops pointing at the second page, so every
viewer stops drawing it, and the text is untouched.

## Why this file exists

It is the cleanest failed redaction in this corpus. Nothing was covered,
nothing was painted invisible, no font trick was used — the page was simply
unreferenced. It is also invisible to any tool that reads what the current
catalogue points at, which is most of them and was all of this one until now.

## Producers, and why two

LibreOffice cannot write an incremental update, so pypdf performs the delete.
It is a real writer used in real pipelines and **it** decides the byte layout,
not this repository — one invented here would prove the detector can read what
this repository invented, which is the mistake `filetrail`'s HEIC reader was
built on.

pypdf is also this project's parser, and a reader agreeing with its own writer
proves close to nothing. Two things answer that. The specimen is checked with
`qpdf`, an independent implementation. And the detector finds revision
boundaries **in the raw bytes**, then proves each one by parsing the prefix
before it — so a `%%EOF` inside a stream costs a failed parse and nothing else.

The builder asserts the original file is a byte-for-byte prefix of the result.
If that ever stops holding, what it produced is not an incremental update and
the specimen is worthless; it fails rather than writing one.

Everything is invented: no such award, no such annex, no such bidder.

## The control

[`libreoffice-writer-metadata-leak.pdf`](libreoffice-writer-metadata-leak.md) —
one revision, like almost every PDF. The detector has to stay silent on it.
