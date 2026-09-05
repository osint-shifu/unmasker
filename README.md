<div align="center">

# unmasker

### What a human sees in a document, against what a machine reads out of it.

**Local, read-only detection of hidden, residual and failed-redaction content in documents.**

[![PyPI](https://img.shields.io/pypi/v/unmasker?style=flat-square&color=3775A9)](https://pypi.org/project/unmasker/)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square)
![27 detectors](https://img.shields.io/badge/detectors-27-8250df?style=flat-square)
![Runtime dependencies](https://img.shields.io/badge/runtime_dependencies-1-1f883d?style=flat-square)
![Local and read-only](https://img.shields.io/badge/local_%26_read--only-yes-1f883d?style=flat-square)
![Network requests](https://img.shields.io/badge/network_requests-none-1f883d?style=flat-square)
[![CI](https://github.com/osint-shifu/unmasker/actions/workflows/ci.yml/badge.svg)](https://github.com/osint-shifu/unmasker/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-Apache--2.0-8250df?style=flat-square)

[Install](#installation) ·
[Usage](#usage) ·
[What it finds](#what-it-finds) ·
[Examples](#practical-examples) ·
[Detector reference](#detector-reference) ·
[Automation](#json-and-automation)

</div>

---

unmasker finds content that survives inside a document but is hidden, covered,
deleted, filtered, cropped or otherwise absent from what a person normally
sees.

A black rectangle drawn over text is not a redaction. The page may look clean
while the original text remains in the file and is still readable by a parser.
unmasker reports that mismatch and stops there - evidence, not a verdict.

```bash
unmasker tests/specimens/pdf/libreoffice-writer-black-bars.pdf
```

```text
  unmasker                                                      4 findings
    tests/specimens/pdf/libreoffice-writer-black-bars.pdf
  ────────────────────────────────────────────────────────────────────────

  ● 22 characters under a black shape at x 117.5-268.7, y           page 1
    684.2-698.5; the rest of the line still reads "Name:"
  │ human sees     ██████████████████████
  │ machine reads  Wanda Testowa-Przyklad

  ● 21 characters under a black shape at x 114.8-259.3, y           page 1
    664.5-678.7; the rest of the line still reads "Email:"
  │ human sees     █████████████████████
  │ machine reads  w.testowa@example.org

  ● 15 characters under a black shape at x 123.1-228.1, y           page 1
    644.7-658.9; the rest of the line still reads "Telephone:"
  │ human sees     ███████████████
  │ machine reads  +48 601 000 000

  ● 37 characters under a black shape at x 119.0-369.1, y           page 1
    624.9-639.2; the rest of the line still reads "Address:"
  │ human sees     █████████████████████████████████████
  │ machine reads  ul. Przykladowa 12/3, 00-001 Warszawa

  notes                                                             1 note
  ────────────────────────────────────────────────────────────────────────
    the file says it was made by Creator Writer; Producer LibreOffice
    24.2, and dates itself CreationDate 2026-08-31T20:25:50Z

  ────────────────────────────────────────────────────────────────────────
  searched 1 page of 1. 4 findings in 1 kind.
  sha256 fbaeef0d794f2bdb6f4c6bb823686a10d1e1b67e6b2d49df5fe33fd9a281f1a5
```

Every finding says what a human sees, what a machine reads, where the mismatch
is and how the tool knows.

That file is a specimen committed to this repository, as is every other
example on this page. Clone it and the commands run.

## Installation

```bash
pipx install unmasker
```

Or:

```bash
uv tool install unmasker
```

Python 3.10 or later. The default install has one runtime dependency: `pypdf`.
unmasker runs locally, makes no network requests and never modifies the file it
is given.

From a checkout:

```bash
git clone https://github.com/osint-shifu/unmasker
cd unmasker
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/unmasker document.pdf
```

## Usage

```text
unmasker <file>   [options]
unmasker <folder> [options]
```

Scan one file:

```bash
unmasker document.pdf
```

Survey a folder:

```bash
unmasker ~/cases/kowalski
```

Produce machine-readable or shareable output:

```bash
unmasker document.pdf --json
unmasker document.pdf --md > report.md
unmasker ~/cases/kowalski --html > report.html
```

| Option | Purpose |
| :--- | :--- |
| `--json` | emit one JSON object on stdout for a pipeline to sort or filter |
| `--html` | emit one self-contained HTML report on stdout |
| `--md` | emit Markdown on stdout for a wiki, ticket or pull request |
| `--ocr` | render a page and read it back to catch mismatches without knowing the hiding technique |
| `--width N` | wrap terminal output at N columns |
| `--version` | print the version and exit |
| `-h`, `--help` | show the full option list |

Exit status is part of the interface:

| Code | Meaning |
| :--- | :--- |
| `0` | read, searched, nothing found |
| `1` | read, searched, findings exist |
| `2` | could not be read |

> **A file that could not be read is not a file that came back clean.**
> unmasker keeps those states separate so a pipeline cannot silently treat
> failure as a clean result.

## What it finds

| Area | Examples |
| :--- | :--- |
| PDF pages | covered text, text under images, invisible text, low contrast, off-page content |
| PDF revisions | pages and text left in the file by an incremental update, which the current document no longer points at |
| Unicode | zero-width characters, bidi controls, tag characters, mixed scripts |
| Word / ODT | tracked deletions, comments, revision history, metadata leaks |
| Excel / Calc | hidden sheets, rows and columns, filtered rows, tracked cell changes |
| PowerPoint / Impress | hidden slides and speaker notes |
| JPEG | stale EXIF thumbnails that can preserve content removed by cropping, and the XMP edit history an editor left behind |
| Metadata | undisclosed values, local filesystem paths and conflicting metadata copies |
| Attachments | whole files carried inside a document, which no page mentions — and what a carried workbook hides in turn |
| OCR comparison | text present in the file but absent from the rendered page, and the reverse |

Supported inputs are PDF, DOCX, ODT, XLSX, ODS, PPTX, ODP, JPEG and UTF-8 text.
Content is identified from the file itself rather than trusted solely from the
extension.

## Practical examples

### Text under an image

```bash
unmasker tests/specimens/pdf/libreoffice-writer-image-over-text.pdf
```

```text
  unmasker                                                       1 finding
    tests/specimens/pdf/libreoffice-writer-image-over-text.pdf
  ────────────────────────────────────────────────────────────────────────

  ● 22 characters under an image at x 123.3-245.9, y 702.8-720.0;   page 1
    an image over a text layer is also what a scan of a printed
    page looks like, and there the two normally agree; the rest of
    the line still reads "Subject:"
  │ human sees     ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
  │ machine reads  Ludmila Wieczorek-Test

  notes                                                             1 note
  ────────────────────────────────────────────────────────────────────────
    the file says it was made by Creator Writer; Producer LibreOffice
    24.2, and dates itself CreationDate 2026-08-31T23:50:46Z

  ────────────────────────────────────────────────────────────────────────
  searched 1 page of 1. 1 finding in 1 kind.
  sha256 d324105840b72c0d76c491150fe9220eabb4a87a3735afdb5de5af4c27fa0b66
```

An image over text is also what a scan of a printed page looks like.
unmasker says so in the finding rather than calling it a redaction.

### Hidden spreadsheet data

```bash
unmasker tests/specimens/xlsx/libreoffice-calc-hidden-columns.xlsx
```

```text
  unmasker                                                      7 findings
    tests/specimens/xlsx/libreoffice-calc-hidden-columns.xlsx
  ────────────────────────────────────────────────────────────────────────

  comment                                                        1 finding
  ────────────────────────────────────────────────────────────────────────
  ● a comment by Halina Probna-Test, at a time the file does    whole file
    not state, carried in the file and not part of the
    document body
  │ human sees     nothing on the page
  │ machine reads  Panel agreed the reserve before the bids were opened.
  │                Not for the file we release.

  revision-history                                               1 finding
  ────────────────────────────────────────────────────────────────────────
  ● the file records 1 comment, by 1 person. A name here is     whole file
    whatever the application that wrote it was configured to
    say
  │ human sees     nothing on the page
  │ machine reads  Halina Probna-Test

  hidden-sheet                                                   1 finding
  ────────────────────────────────────────────────────────────────────────
  ● sheet "Workings" is marked hidden, and holds 1 value still  whole file
    in the file
  │ human sees     nothing on the page
  │ machine reads  Reserve set at 240,000. Kowalski came in 12% under; the
  │                others were told nothing.

  hidden-rows                                                    1 finding
  ────────────────────────────────────────────────────────────────────────
  ● row 4 of sheet "Evaluation" is hidden, and holds 6 values   whole file
    still in the file
  │ human sees     nothing on the page
  │ machine reads  Delta Consulting sp. z o.o. | 82 | 44 | 196000 | 63 |
  │                withdrawn after the deadline - do not list

  hidden-columns                                                 1 finding
  ────────────────────────────────────────────────────────────────────────
  ● column D of sheet "Evaluation" is hidden, and holds 5       whole file
    values still in the file
  │ human sees     nothing on the page
  │ machine reads  Reserve price (EUR) | 211000 | 238000 | 196000 | 251000

  undisclosed-metadata                                          2 findings
  ────────────────────────────────────────────────────────────────────────
  ● the creator field of docProps/core.xml holds a value the    whole file
    document does not show anywhere in its text
  │ human sees     nothing on the page
  │ machine reads  Halina Probna-Test

  ● the title field of docProps/core.xml holds a value the      whole file
    document does not show anywhere in its text
  │ human sees     nothing on the page
  │ machine reads  Tender evaluation - panel copy

  notes                                                             1 note
  ────────────────────────────────────────────────────────────────────────
    the file says it was made by Application
    LibreOffice/24.2.7.2$Linux_X86_64 LibreOffice_project/420$Build-2;
    AppVersion 15.0000, and counts revision 0; TotalTime 0

  ────────────────────────────────────────────────────────────────────────
  searched the text of this file. 7 findings in 6 kinds.
  sha256 6cb60d45c5e8fe7b2c05c1eee565ec417079909800f48209c88b28c42ec53c8e
```

### Case-folder triage

```bash
unmasker tests/specimens/docx
```

```text
  unmasker  tests/specimens/docx                              4 of 8 files
  ────────────────────────────────────────────────────────────────────────
    read      8 files, 17 findings
    not read  0 files

  what was found                                                  11 kinds
  ────────────────────────────────────────────────────────────────────────
    attached-file         1 file
    hidden-sheet          1 file
    zero-width            1 file
    bidi-control          1 file
    tag-characters        1 file
    mixed-script          1 file
    undisclosed-metadata  1 file
    metadata-path         1 file
    deleted-text          1 file
    comment               1 file
    revision-history      1 file

  files that hide something                                        4 files
  ────────────────────────────────────────────────────────────────────────
    libreoffice-writer-embedded-sheet.docx     attached-file, hidden-sheet
    libreoffice-writer-hidden-characters.docx  zero-width, bidi-control,
                                               tag-characters,
                                               mixed-script
    libreoffice-writer-metadata-leak.docx      undisclosed-metadata,
                                               metadata-path
    libreoffice-writer-tracked-changes.docx    deleted-text, comment,
                                               revision-history

  ────────────────────────────────────────────────────────────────────────
  searched 8 files. unmasker <file> for the detail, --json for all of it.
```

A directory scan reports what was read, what could not be read, which detector
kinds appeared and which files contain findings. It does not rank files by
"severity". Use the detailed file report or `--json` for every finding.

### Read the rendered page back

```bash
unmasker scan.pdf --ocr
```

`--ocr` asks a different question: does the text stored in the document agree
with the page after it is rendered? This can expose a hiding technique for
which there is no dedicated detector yet.

For PDF page comparison it requires `ghostscript` and `tesseract` on `PATH` and
costs seconds per page, so it is intentionally opt-in and refused for directory
surveys.

## Detector reference

The detector slug is stable output intended for reports and automation.

### Page and rendering

| Detector | What it reports |
| :--- | :--- |
| `covered-text` | text underneath a filled shape, measured per character |
| `text-under-image` | text underneath an image, kept distinct from a filled-shape redaction |
| `invisible-text` | text that the page's rendering instructions do not paint |
| `low-contrast-text` | text too close in colour to the background behind it |
| `off-page-text` | text outside the visible page or crop box |
| `unrendered-text` | words stored in the file that OCR cannot find on the rendered page |
| `unextractable-text` | words visible to OCR on the rendered page but absent from the extracted text |

### Characters

| Detector | What it reports |
| :--- | :--- |
| `zero-width` | zero-width spaces, joiners, soft hyphens and word joiners |
| `bidi-control` | Unicode direction controls that can change how a string appears on screen |
| `tag-characters` | plane-14 Unicode tag characters, decoded when possible |
| `mixed-script` | a single word containing characters from multiple scripts |

### Spreadsheets

| Detector | What it reports |
| :--- | :--- |
| `hidden-sheet` | a hidden or very-hidden sheet that still carries values |
| `hidden-rows` | hidden rows that still carry values, collapsed into blocks |
| `hidden-columns` | hidden columns that still carry values |
| `filtered-rows` | rows currently excluded by a worksheet filter |
| `changed-cell` | a tracked cell change, including the replaced value when available |

### Presentations

| Detector | What it reports |
| :--- | :--- |
| `hidden-slide` | a slide stored in the deck but skipped when the presentation is shown |
| `speaker-notes` | speaker-note text that never appears on the projected slide |

### Images

| Detector | What it reports |
| :--- | :--- |
| `stale-thumbnail` | an embedded EXIF preview whose dimensions show it was not regenerated from the current image |

### Container, revisions and metadata

| Detector | What it reports |
| :--- | :--- |
| `deleted-text` | text preserved inside a tracked deletion |
| `comment` | comments and annotations stored with the document |
| `revision-history` | document revision authorship and edit history |
| `undisclosed-metadata` | metadata values that do not appear in the document's visible text |
| `metadata-path` | filesystem paths exposed by document metadata |
| `metadata-conflict` | contradictory copies of metadata stored inside the same file |
| `attached-file` | a whole file carried inside the document, on no page and not printed with it |
| `earlier-revision` | text an earlier revision of the file still holds, which no page shows now |

## Evidence model

unmasker reports observable mismatches. It does not decide whether a document
is malicious, manipulated or safe.

Each finding carries one of three evidence bases:

- **direct** - the relevant bytes are in the file and were read out directly
- **circumstantial** - the observation is consistent with hiding, but an innocent explanation can also fit
- **self-reported** - the document or application reports the fact about itself

There are no severity scores or synthetic confidence percentages. Different
questions are not ranked against each other.

> **"Nothing found" and "nothing could be searched" are different results.**
> unmasker keeps them separate. JSON exposes this explicitly through the
> `searched` field.

Values are not shortened with ellipses. If evidence is long, the report wraps
it instead of silently dropping part of it.

## Reports

The terminal report is for triage. Three stdout formats are available when the
result needs to be stored, processed or sent to someone else:

- `--json` for automation
- `--html` for a self-contained human-readable report
- `--md` for Markdown-based systems

unmasker treats report content as untrusted because every quoted value came
from a file being investigated. HTML values are escaped, Markdown evidence is
fenced or escaped, and generated HTML contains no JavaScript or external
resources.

The tool has no `--out` option. Redirection keeps the core rule simple:
unmasker itself never writes to the input or to the case directory.

## JSON and automation

`--json` writes one object on stdout while the exit status remains usable as a
pipeline gate:

```bash
unmasker document.pdf --json > findings.json || echo "findings exist"
```

The JSON shape is versioned separately from the package version:

| Field | Meaning |
| :--- | :--- |
| `schema` | `unmasker.scan/1` for one file or `unmasker.survey/1` for a folder |
| `version` | the unmasker build that produced the report |
| `searched` | `false` means there was nothing to search, not that a search came back empty |
| `sha256` | the digest of the bytes that were read, so a finding can be checked against the file rather than the path |
| `location.inside` | present when a finding came out of a file the document carries, naming it |

```bash
unmasker tests/specimens/pdf/libreoffice-writer-image-over-text.pdf --json
```

```json
{
  "tool": "unmasker",
  "schema": "unmasker.scan/1",
  "version": "0.1.12",
  "file": "tests/specimens/pdf/libreoffice-writer-image-over-text.pdf",
  "sha256": "d324105840b72c0d76c491150fe9220eabb4a87a3735afdb5de5af4c27fa0b66",
  "kind": "pdf",
  "searched": true,
  "remarks": [
    "the file says it was made by Creator Writer; Producer LibreOffice 24.2, and dates itself CreationDate 2026-08-31T23:50:46Z"
  ],
  "findings": [
    {
      "detector": "text-under-image",
      "basis": "direct",
      "summary": "22 characters under an image at x 123.3-245.9, y 702.8-720.0; an image over a text layer is also what a scan of a printed page looks like, and there the two normally agree; the rest of the line still reads \"Subject:\"",
      "human_sees": "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒",
      "machine_reads": "Ludmila Wieczorek-Test",
      "location": {
        "page": 1
      },
      "codepoints": [
        "U+004C",
        "U+0075",
        "U+0064",
        "U+006D",
        "U+0069",
        "U+006C",
        "U+0061",
        "U+0020",
        "U+0057",
        "U+0069",
        "U+0065",
        "U+0063",
        "U+007A",
        "U+006F",
        "U+0072",
        "U+0065",
        "U+006B",
        "U+002D",
        "U+0054",
        "U+0065",
        "U+0073",
        "U+0074"
      ]
    }
  ]
}
```

The `/1` changes only when the JSON shape changes incompatibly. A normal
package release does not force downstream consumers to guess whether their
parser still works.

## Design principles

- **Evidence, not verdicts.** Report what can be shown and leave interpretation to the analyst.
- **Absence is explicit.** Unreadable, unsearched and searched-with-no-findings are different states.
- **Read-only.** Input files are never modified.
- **Local.** No uploads and no network requests.
- **Real specimens.** Detectors are tested against files produced by real applications, not only hand-built fixtures.
- **No hidden ranking.** Findings are grouped by what was observed, not by an invented severity score.

### What unmasker is not

unmasker is not a malware scanner, DLP system, authenticity classifier or
forensic verdict engine. It exposes discrepancies and residual content so a
human or a downstream system can decide what they mean.

## How it is tested

Every detector fires on a committed specimen written by a real producer,
including LibreOffice, headless Chrome, Ghostscript, Tesseract, exiftool and
ImageMagick. There are 38 of them and each has a provenance note describing how
it was produced, what a person sees and what is actually stored inside.

This matters because real producers routinely disagree with assumptions made
from a file-format specification. The first PDF specimen, for example, showed
that LibreOffice represented a redaction bar differently from the shape the
initial detector design expected.

Independent tooling such as Poppler is used where specimens need measurements,
and detector behavior is mutation-tested so a broken rule has to break a test.
The README is checked against the repository so the front page cannot silently
drift away from the code: the detector list, the detector badge, the specimen
count, the test count, and every example on this page - each command is run
and its output compared to the block printed beneath it.

748 tests.

## Limits

- No verdicts about whether a document was manipulated or malicious.
- No writing to the input file and no network access.
- Legacy OLE2 formats such as `.doc`, `.xls` and `.ppt` are not supported.
- Signature coverage is not checked. A signed PDF's `/ByteRange` says which bytes it covers, and no signed specimen could be produced to test a detector against.
- XMP is read in PDF and JPEG. DOCX and TIFF carry packets too and are not read yet.
- Producer coverage is not universal. Microsoft Word and Adobe Acrobat are not part of the current specimen corpus, and different producers can encode the same feature differently.
- OCR is optional, slower than structural detection and depends on external tools.

See [`tests/specimens/README.md`](tests/specimens/README.md) for the current
producer coverage and explicitly documented gaps.

## Development

```bash
git clone https://github.com/osint-shifu/unmasker
cd unmasker
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

Project references:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) - development and specimen rules
- [`SECURITY.md`](SECURITY.md) - security policy and threat model
- [`CHANGELOG.md`](CHANGELOG.md) - release history
- [`tests/specimens/README.md`](tests/specimens/README.md) - specimen provenance and coverage gaps

## License

Apache License 2.0.

---

<div align="center">

**unmasker**

*What a human sees in a document, against what a machine reads out of it.*

Made by [osint-shifu](https://github.com/osint-shifu)

</div>
