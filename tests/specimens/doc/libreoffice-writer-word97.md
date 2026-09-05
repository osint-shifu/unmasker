# `libreoffice-writer-word97.doc`

**Producer:** LibreOffice 24.2 Writer, exported to Word 97. Built by
[`sources/build_legacy_word.py`](../sources/build_legacy_word.py).

## What a person sees

One paragraph: an award notice saying the contract has been awarded and the
file is closed. It names nobody.

## What is stored inside

A **compound file** — a FAT filesystem in a single file, with a second smaller
filesystem nested inside it. Seven streams:

| Stream | Bytes | |
| :--- | ---: | :--- |
| `Root Entry` | 6208 | the mini stream itself |
| `\x01CompObj` | 106 | OLE bookkeeping |
| `\x01Ole` | 20 | OLE bookkeeping |
| `1Table` | 1783 | Word's tables |
| `WordDocument` | 3631 | the text, in a binary format |
| `\x05SummaryInformation` | 368 | Title, Subject, Author, Keywords, Last Saved By, Revision Number |
| `\x05DocumentSummaryInformation` | 184 | Company, in a user-defined section |

The metadata names two different people, a title marked *do not circulate*, and
a company. None of it is on the page.

## Why this file exists before the reader did

**Every stream here is under the 4096-byte cutoff**, so every one of them lives
in the mini stream rather than in sectors. A compound-file reader written from
the specification is entitled to implement full sectors first and leave the
mini stream for later — and against this file, which is an entirely ordinary
one, it would read **nothing at all** while passing any test suite built the
same way it was.

That is the HEIC failure exactly: `filetrail`'s reader took the first
`Exif\0\0` in the file, which the specification does describe, and decoded
nothing from any real HEIC while its suite stayed green.

Two further things came out of this file rather than out of the specification.

The **code page** is declared in the file, as property 1, and here it is 65001.
Assuming the specification's usual CP1252 gives the right answer for plain
ASCII and mangles every name with a diacritic in it.

**Company is not where the specification says.** It is not property 15 of
`DocumentSummaryInformation`; LibreOffice writes it into a second section under
`FMTID_UserDefinedProperties`, where names are not numbers at all but entries
in a dictionary stored as property 0. A reader built to the specification finds
nothing there.

## What this specimen does not cover

The `WordDocument` stream. Its text is a binary format with a piece table, and
none of it is read — which is why the report says this file's text *was not
read* rather than that it has none, and why no metadata value here is called
undisclosed. Nothing compared them against a page.

Producers other than LibreOffice. Word itself is not on this machine. The
container reader was checked against two Excel 97 workbooks written by
something else, which parsed and gave up their property streams; those files
are the author's own and are not in this repository.

Everything in the metadata is invented.
