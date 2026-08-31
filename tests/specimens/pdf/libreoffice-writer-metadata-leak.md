# libreoffice-writer-metadata-leak.pdf

The same source document as
[`../docx/libreoffice-writer-metadata-leak.docx`](../docx/libreoffice-writer-metadata-leak.md),
exported to the other container. The page is the same anonymous sentence; what
survives into the metadata is not the same, and that is why both are committed.

- 10 130 bytes, `sha256:d49d77ec9b3749ee…`
- `/Producer` `LibreOffice 24.2`, `/Creator` `Writer`

## How it was made

The second output of the shared builder — see the DOCX specimen for the
command and for the source document.

## What is actually in the file

| field | value | role |
| --- | --- | --- |
| `/Author` | `Marek Wysocki-Test` | content |
| `/Title` | `Board briefing - restricted` | content |
| `/Subject` | `Project Harrow` | content |
| `/Keywords` | `confidential, do not circulate` | content |
| `/Creator` | `Writer` | **tool** |
| `/Producer` | `LibreOffice 24.2` | **tool** |
| `/CreationDate` | a timestamp | time |

Four findings, against the DOCX's seven.

## What the two containers prove between them

**The PDF export drops the custom properties.** `Client` and `SourceTemplate`
are in the .docx and not here, so the path never reaches the PDF. A tool tried
on only one container would have a confident and partial idea of what metadata
is, and this pair is what stops that.

**It also drops `cp:lastModifiedBy`.** The .docx names two people; the PDF
names one.

**`/Creator` means something else here.** In a PDF it is the application that
made the original document — `Writer`. In OOXML, `dc:creator` is a person —
`Marek Wysocki-Test`. One field name, two meanings, and only the container
tells them apart. `test_the_same_field_name_means_different_things_in_different_containers`
is the assertion that keeps them apart, and getting it wrong would either
report an application as a person or hide a person as an application.
