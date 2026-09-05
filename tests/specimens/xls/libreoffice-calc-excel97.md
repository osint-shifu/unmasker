# `libreoffice-calc-excel97.xls`

**Producer:** LibreOffice 24.2 Calc, exported to Excel 97. Built by
[`sources/build_legacy_excel.py`](../sources/build_legacy_excel.py).

## What a person sees

A two-column sheet named *Scores*: one bidder and one number.

## Why it is here

**To hold a negative claim still.**

`.doc`, `.xls` and `.ppt` are all compound files, and until `unmasker.word`
landed the same sentence covered all three: *its text is stored in a binary
format this tool does not read*. Word's text is read now. This file exists so
that the sentence cannot quietly be loosened to keep passing once the format
it was written about became readable — which is how a report ends up
describing a search that never happened.

A workbook must go on saying its text was not read, must go on refusing to
call any metadata value *undisclosed* — nothing compared it against anything —
and must go on giving up both property streams. Four tests say so, and this is
the file they say it about.

`Workbook` is a BIFF record stream: a different format again, not a piece
table, and none of it is implemented.

## What is stored inside

| Stream | |
| :--- | :--- |
| `Workbook` | the cells, in BIFF records, unread |
| `\x05SummaryInformation` | Title, Last Saved By, Revision Number |
| `\x05DocumentSummaryInformation` | Company, in a user-defined section |
| `\x01CompObj`, `\x01Ole` | OLE bookkeeping |

Everything in the metadata and the cells is invented.
