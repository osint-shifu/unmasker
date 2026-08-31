# libreoffice-writer-metadata-leak.docx

One anonymous sentence on the page. Two people, a client, a codename, a
classification and somebody's home directory in the file.

Paired with [`../pdf/libreoffice-writer-metadata-leak.pdf`](../pdf/libreoffice-writer-metadata-leak.md),
which is the same source document exported to the other container. They carry
different amounts of it, and that difference is the point of having both.

- 5 519 bytes, `sha256:a9b8e954b09bed07…`
- produced by LibreOffice 24.2 Writer

## How it was made

```bash
python3 tests/specimens/sources/build_metadata_leak.py \
    tests/specimens/docx/libreoffice-writer-metadata-leak.docx \
    tests/specimens/pdf/libreoffice-writer-metadata-leak.pdf
```

One Flat ODF source with an `<office:meta>` block, converted twice.

## What a human sees

```text
The board notes the position and will revert in due course.
```

That is the whole document. No name, no client, no classification.

## What is actually in the file

| part | field | value |
| --- | --- | --- |
| `docProps/core.xml` | `dc:creator` | `Marek Wysocki-Test` |
| `docProps/core.xml` | `cp:lastModifiedBy` | `Ewa Zielinska-Test` |
| `docProps/core.xml` | `dc:title` | `Board briefing - restricted` |
| `docProps/core.xml` | `dc:subject` | `Project Harrow` |
| `docProps/core.xml` | `cp:keywords` | `confidential, do not circulate` |
| `docProps/custom.xml` | `Client` | `Acme Holdings BV` |
| `docProps/custom.xml` | `SourceTemplate` | `/home/mwysocki/Templates/acme-board-restricted.ott` |
| `docProps/app.xml` | `TotalTime` | `252` — four hours and twelve minutes of editing |
| `docProps/core.xml` | `cp:revision` | `37` |

The path names an account, a directory structure and the client again.

## The field that must stay a remark

```text
Application  LibreOffice/24.2.7.2$Linux_X86_64 LibreOffice_project/420$Build-2
```

This is the worked example from `CLAUDE.md`, and it turned up here without
being arranged. It contains a dotted quad. Pattern-matching alone reports an IP
address; the field is called `Application`, so it is a version.

`test_a_version_in_an_application_field_is_not_read_as_an_address` holds the
tool to that, and a second test checks it end to end: the string must appear in
the report's notes and in none of its findings.

## What it is for

Two rules at once.

**Most metadata is not a finding.** `Application`, `AppVersion`, the dates and
the counts are remarks. Every .docx has them, and a tool that reported them
would exit non-zero on every document ever written — which would make the exit
code, the whole CI gate this project has instead of a `--strict` mode, mean
nothing.

**What the document does not show is.** A value is reported when the
document's own text does not contain it. That is the same rule the rest of the
tool runs on, applied to a part of the file rather than to a part of the page.
