<div align="center">

# Unmasker

### What a human sees in a document, against what a machine reads out of it.

**Local, read-only detection of hidden and failed-redaction content in documents.**

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square)
![25 detectors](https://img.shields.io/badge/detectors-25-8250df?style=flat-square)
![Runtime dependencies](https://img.shields.io/badge/runtime_dependencies-1-1f883d?style=flat-square)
![Local and read-only](https://img.shields.io/badge/local_%26_read--only-yes-1f883d?style=flat-square)
![Network requests](https://img.shields.io/badge/network_requests-none-1f883d?style=flat-square)
[![CI](https://github.com/osint-shifu/unmasker/actions/workflows/ci.yml/badge.svg)](https://github.com/osint-shifu/unmasker/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-Apache--2.0-8250df?style=flat-square)

[Why Unmasker?](#why-unmasker) ·
[What it finds](#what-it-finds) ·
[Install](#installation) ·
[Usage](#usage) ·
[Examples](#practical-examples) ·
[How it decides](#how-it-decides-what-to-say) ·
[JSON](#json-and-automation)

</div>

---

A black rectangle drawn over text is not a redaction. The text is still in the
file and every parser reads it. `unmasker` reports each place the two layers
disagree — and says nothing beyond what it can show.

```console
$ unmasker leaked.pdf

  unmasker  leaked.pdf                                          4 findings
  ────────────────────────────────────────────────────────────────────────

  ● 22 characters under a black shape at x 117.5-268.7, y           page 1
    684.2-698.5; the rest of the line still reads "Name:"
  │ human sees     ██████████████████████
  │ machine reads  Wanda Testowa-Przyklad

  ● 21 characters under a black shape at x 114.8-259.3, y           page 1
    664.5-678.7; the rest of the line still reads "Email:"
  │ human sees     █████████████████████
  │ machine reads  w.testowa@example.org
```

Every finding names the two readings, where to look, and how the tool knows.
There are no verdicts: it does not say a document was manipulated, because
that is the reader's conclusion to draw and a tool that draws it has to be
trusted blindly.

## Why Unmasker?

The person redacting a document sees a black bar and believes the job is done.
It keeps happening in court filings and government releases, because the tool
that draws the bar does not remove what is under it.

The same reading serves two more uses. A PDF fed to a retrieval pipeline can
carry instructions a human reviewer will never see. And a leaked or altered
document can be checked: what did the tracked changes hold, whose name is in
the metadata, does the text layer agree with the picture.

## What it finds

### On the page

| Detector | What it reports |
| :--- | :--- |
| `covered-text` | text under a filled shape, reported per character — a bar dragged too short is reported as covering exactly what it covers |
| `text-under-image` | text under a picture, kept separate because a scan of a printed page looks the same and usually agrees with itself |
| `invisible-text` | text a render mode never paints, or an opacity that paints nothing — `color: transparent` is one CSS declaration and changes no render mode at all |
| `low-contrast-text` | text in the colour of what is behind it, whether that is a shape or the bare paper |
| `off-page-text` | text outside the visible page — a crop box smaller than the media box is how a "cropped" file keeps what was cropped off |

### In the characters

Works on anything that yields text, so it covers DOCX, HTML, Markdown and
source as well as PDF.

| Detector | What it reports |
| :--- | :--- |
| `zero-width` | zero-width spaces, joiners, soft hyphens, word joiners |
| `bidi-control` | direction overrides — a filename written `invoice⟨U+202E⟩gpj.exe` in the file reads as `invoiceexe.jpg` on screen, and is an executable |
| `tag-characters` | plane-14 tag characters, decoded; the channel of choice for hiding instructions in text meant for a model |
| `mixed-script` | a single word spanning two scripts — Cyrillic `а` inside a Latin domain |

### In a spreadsheet

A row, a column or a whole sheet carries an attribute saying not to draw it,
and every value in it stays in the file exactly as typed. Someone selects three
columns, right-clicks, chooses Hide, and sends the workbook out believing the
numbers are gone.

| Detector | What it reports |
| :--- | :--- |
| `hidden-sheet` | a sheet the workbook carries and never shows — and it says so louder when the sheet is marked `veryHidden`, which the application offers no way to undo |
| `hidden-rows` | rows nobody sees, collapsed into one finding per block, because hiding rows 10 to 40 is one act by one person |
| `hidden-columns` | the same by column, addressed the way the person who hid it saw it: `column D`, not an index |
| `filtered-rows` | rows a filter is holding back rather than a person having hidden them — a weaker claim, and reported as one |
| `changed-cell` | what change tracking took out of a cell and left in the file, with who changed it and when — the one finding here whose **both** columns carry text, because the current value is sitting in the cell |

A spreadsheet stores a date as `45366` and a price as `240000`. Dates are
rendered, because a date cell holds a count of days and the conversion is
exact. Everything else is quoted as the file stores it, with a note naming the
format the sheet applies — a number formatter that is nearly right quotes a
figure that is nearly right, which is worse than an exact quotation and a
sentence of context.

### In a presentation

| Detector | What it reports |
| :--- | :--- |
| `hidden-slide` | a slide the deck skips when it is shown, quoted in full — the one that was cut before the meeting and never deleted |
| `speaker-notes` | a note that was never on the screen, which is what notes are for and why the candid line ends up in one |

### In a photograph

A picture has no text layer, so the question inverts: not *what does this
document say that it does not show*, but *what does this file show that the
picture does not*.

| Detector | What it reports |
| :--- | :--- |
| `stale-thumbnail` | the preview in the EXIF is a different shape from the picture, so it was not made from it — cropping a photograph does not regenerate the preview, and ImageMagick carries the old one through unasked |

With `--ocr` the same file is asked the stronger question: what is legible in
the preview and absent from the picture. On the specimen that is the witness
name the crop removed.

### In the container

| Detector | What it reports |
| :--- | :--- |
| `deleted-text` | what a tracked deletion took off the page and left in the file, with who deleted it and when |
| `comment` | comments — in Word, in OpenDocument, and in a PDF where they are annotations hanging off the page that no text extraction reports |
| `revision-history` | one line naming who edited the file and when, never one finding per change |
| `undisclosed-metadata` | a name, a client, a codename or a classification the document's own text never shows |
| `metadata-path` | a filesystem path, which leaks a directory structure and usually an account |
| `metadata-conflict` | the file contradicting itself — a PDF states its metadata twice, and a tool that clears one copy and not the other leaves exactly that |

### By reading the page back

`--ocr` renders each page and reads the picture with an OCR engine. It needs
`ghostscript` and `tesseract`, and costs seconds a page, which is why it is not
the default.

| Detector | What it reports |
| :--- | :--- |
| `unrendered-text` | words the file holds that the page does not show — **found without knowing how they are hidden** |
| `unextractable-text` | words the page shows that the file does not hold; the only finding here where the two columns swap |

Every other detector knows a trick, and each was written after a producer was
caught doing something particular. This one knows nothing, so a method nobody
has thought of still fails it. On the specimens the two approaches name the
same words on every file that hides text, and both stay silent on every
control — which is not something either could arrange for the other.

## Installation

Not published anywhere yet, so it is installed from a checkout of this
repository:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/unmasker document.pdf
```

Python 3.10 or later, and one runtime dependency — `pypdf`, which is pure
Python, BSD-licensed and has no dependencies of its own. It was checked rather
than assumed, and any second one has to earn its place the same way — in
writing.

Reads PDF, DOCX, ODT, XLSX, ODS, PPTX, ODP, JPEG and any text file. Local,
read-only, no network, and it never writes to the file it is given.

## Usage

```text
unmasker <file>   [options]
unmasker <folder> [options]
```

Point it at a **folder** and it surveys the lot: how much was read, how much
could not be, which kinds of finding turned up and in how many files, and which
files to open next. The screen triages and `--json` carries every finding, so
there is no `--full` — the archive already exists.

It never ranks the files. Sorting the worst documents to the top would be the
judgement this tool leaves to its reader, so the tally counts files per kind
and the list is in path order.

| Option | Purpose |
| :--- | :--- |
| `--json` | one object on stdout, for a pipeline that wants to sort or filter |
| `--html` | one self-contained page on stdout — redirect it into a file and send it |
| `--md` | Markdown on stdout, for a wiki, a ticket or a pull request |
| `--ocr` | render each page and read the picture back (needs `ghostscript`, `tesseract`) |
| `--width N` | wrap at N columns instead of measuring the terminal |
| `--version` | print the version and exit |
| `-h`, `--help` | the full option list |

| Code | Meaning |
| :--- | :--- |
| `0` | read, searched, nothing found |
| `1` | read, searched, findings exist |
| `2` | could not be read |

> [!IMPORTANT]
> Three exit statuses rather than two, because **a file that could not be read
> is not a file that came back clean**. A pipeline that cannot tell those apart
> will eventually wave through the one document it should have stopped.

## Practical examples

### One document, reported for a person

```bash
unmasker tests/specimens/pdf/libreoffice-writer-black-bars.pdf
```

```text
  unmasker  libreoffice-writer-black-bars.pdf                     4 findings
  ──────────────────────────────────────────────────────────────────────────

  ● 22 characters under a black shape at x 117.5-268.7, y             page 1
    684.2-698.5; the rest of the line still reads "Name:"
  │ human sees     ██████████████████████
  │ machine reads  Wanda Testowa-Przyklad

  ● 15 characters under a black shape at x 123.1-228.1, y             page 1
    644.7-658.9; the rest of the line still reads "Telephone:"
  │ human sees     ███████████████
  │ machine reads  +48 601 000 000

  notes                                                               1 note
  ──────────────────────────────────────────────────────────────────────────
    the file says it was made by Creator Writer; Producer LibreOffice 24.2,
    and dates itself CreationDate 2026-08-31T20:25:50Z

  ──────────────────────────────────────────────────────────────────────────
  searched 1 page of 1. 4 findings in 1 kind.
```

### A workbook whose columns were hidden rather than removed

```bash
unmasker tests/specimens/xlsx/libreoffice-calc-hidden-columns.xlsx
```

```text
  hidden-sheet                                                     1 finding
  ──────────────────────────────────────────────────────────────────────────
  ● sheet "Workings" is marked hidden, and holds 1 value still    whole file
    in the file
  │ human sees     nothing on the page
  │ machine reads  Reserve set at 240,000. Kowalski came in 12% under; the
  │                others were told nothing.

  hidden-columns                                                   1 finding
  ──────────────────────────────────────────────────────────────────────────
  ● column D of sheet "Evaluation" is hidden, and holds 5 values  whole file
    still in the file
```

### A folder, surveyed: which file to open next

```bash
unmasker tests/specimens/docx
```

```text
  unmasker  tests/specimens/docx                                3 of 6 files
  ──────────────────────────────────────────────────────────────────────────
    read      6 files, 15 findings
    not read  0 files

  what was found                                                     9 kinds
  ──────────────────────────────────────────────────────────────────────────
    zero-width            1 file
    bidi-control          1 file
    tag-characters        1 file
    mixed-script          1 file
    undisclosed-metadata  1 file
    metadata-path         1 file
    deleted-text          1 file
    comment               1 file
    revision-history      1 file

  files that hide something                                          3 files
  ──────────────────────────────────────────────────────────────────────────
    libreoffice-writer-hidden-characters.docx  zero-width, bidi-control,
                                               tag-characters, mixed-script
    libreoffice-writer-metadata-leak.docx      undisclosed-metadata,
                                               metadata-path
    libreoffice-writer-tracked-changes.docx    deleted-text, comment,
                                               revision-history

  ──────────────────────────────────────────────────────────────────────────
  searched 6 files. unmasker <file> for the detail, --json for all of it.
```

### A page somebody can be sent

```bash
unmasker ~/cases/kowalski --html > report.html
```

One file, no external anything, no JavaScript, and print rules for the day it
goes into a case file. It carries the **full** detail rather than the survey's
summary — a browser has search and a scrollbar where a terminal has neither.

### When the technique is unknown

```bash
unmasker scan.pdf --ocr
```

## Report safety

Everything this tool quotes came out of a document somebody else wrote. That
makes every report an untrusted document too, and the two shareable formats
are escaped accordingly.

`--html` writes to stdout and is redirected, rather than taking an `--out`
option, because this tool never writes anything. Every value on the page is
escaped: a PDF whose metadata reads `<img src=x onerror=…>` would otherwise put
a live handler into the report of itself.

> [!WARNING]
> `--md` is the **more** dangerous of the two to get wrong, not the safer. An
> HTML renderer handed `<script>` prints it; a Markdown renderer runs it,
> because passing raw HTML through is what Markdown does.

So quoted evidence goes in a fenced block — with a fence grown longer than any
run of backticks inside it — prose is escaped, and a `|` never reaches a table
cell unescaped.

## How it decides what to say

**Colour encodes how the tool knows, never how bad it is.** Three classes,
learned once:

- **direct** — the bytes are in the file and were read out; nothing is inferred
- **circumstantial** — consistent with hiding, and with innocent explanations
  too. A word spanning two scripts may be an attack or may be how somebody
  writes; OCR failing to read text looks exactly like text not being there
- **self-reported** — the file's own account of itself. A name in a document is
  whatever the application that wrote it was configured to say

There are no scores. `55` reads as a probability and never was one; a word can
be argued with by the person reading the report, which is the point.

**Different questions are never ranked against each other.** A page can have a
bar over its text *and* an invisible character *and* stale metadata. Those are
three findings, not one winner.

> [!NOTE]
> **"Nothing found" has two meanings**, and the report keeps them apart.
> *Searched and it is not there* is one. *There was nothing this tool could
> search* is the other — a page with no text layer, or text sitting on a
> picture whose colour at that point is not in the file. The second comes with
> a note saying so, and `--json` carries it as `"searched": false`.

**Nothing is truncated.** A value too long for the line wraps. An ellipsis sends
the reader to fetch the value another way, which defeats having read the report.

## JSON and automation

`--json` writes one object on stdout. The exit status still gates, so a
pipeline needs no second mode:

```bash
unmasker leaked.pdf --json > findings.json || echo "findings exist"
```

Two shapes, named in the document itself:

| Field | Meaning |
| :--- | :--- |
| `schema` | `unmasker.scan/1` for one file, `unmasker.survey/1` for a folder. The two carry different keys and this is what tells them apart |
| `version` | which build wrote the document — a different question from which shape it is |
| `searched` | `false` means there was nothing to search, not that the search came back empty |

```json
{
  "tool": "unmasker",
  "schema": "unmasker.scan/1",
  "version": "0.1.0",
  "file": "leaked.pdf",
  "kind": "pdf",
  "searched": true,
  "remarks": ["…"],
  "findings": [
    {
      "detector": "covered-text",
      "basis": "direct",
      "summary": "22 characters under a black shape at x 117.5-268.7, y 684.2-698.5; the rest of the line still reads \"Name:\"",
      "human_sees": "██████████████████████",
      "machine_reads": "Wanda Testowa-Przyklad",
      "location": { "page": 1 },
      "codepoints": ["U+0057", "U+0061", "…"]
    }
  ]
}
```

The field order is deliberate and is the order a consumer sees. `codepoints`
carries every codepoint behind the finding rather than a sample, for the same
reason nothing on the screen is truncated. A folder survey replaces `file` with
`root` and nests the same per-file objects under `files`.

The `/1` is what lets the shape change later without silently breaking anything
built against it.

## How it is tested

Every detector fires on a **committed specimen that a real producer wrote** —
LibreOffice, headless Chrome, Ghostscript, tesseract, exiftool, ImageMagick.
There are 32 of them and they are the test suite; each has a `.md` beside it
recording which tool made it, what a human sees when it is opened, and what is
actually inside.

That discipline is not decoration. The first specimen disproved the design:
LibreOffice draws a redaction bar as a polygon filled with `f*` and emits no
`re` at all, so the rectangle-based detector the plan called for would have
found **nothing** on the archetypal case — and a fixture built from the PDF
specification would have hidden that behind a green test suite.

Where a specimen needs a measurement — where a bar goes, how wide a glyph is —
it comes from **poppler**, not from this project's own code. A fixture measured
with the tool under test proves only that the tool agrees with itself.

Findings are also mutation-tested: each rule is broken on purpose and the suite
has to notice. That has repeatedly found behaviour the docstrings claimed and
nothing checked.

The detector tables above are held against the source by
[`tests/test_documented_detectors.py`](tests/test_documented_detectors.py):
every slug the code can emit has to appear in a table, every slug in a table has
to be one the code emits, and the badge has to agree with both. This document
went stale once — it claimed 22 detectors against 25 — and a number beside a
list does not keep itself true.

716 tests.

## Limits

- **No verdicts.** It will not tell you a document was manipulated.
- **No writing.** It never modifies the file it is given.
- **No network.**
- **Not every container.** Legacy OLE2 (`.doc`, `.xls`, `.ppt`) is unread, and
  so is XMP outside a PDF. The sibling project `filetrail` reads several of
  those and answers a different question with them — where a file came from.
- **Not every producer.** Word and Acrobat are not on the machine this was
  built on, and two producers never agree about everything.
  [`tests/specimens/README.md`](tests/specimens/README.md) keeps the current
  list of what is untested and why.

## Development

```bash
git clone https://github.com/osint-shifu/unmasker
cd unmasker
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

`ruff check .`, and **not** `ruff format --check .`. This project lints and does
not auto-format: the report layout, the specimens' XML and the docstrings are
placed deliberately, and a formatter run at publication time would rewrite a
dozen files nobody asked it to. CI asserts the standard the project actually
holds.

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — the rules this project works to, each
  one named after the failure that produced it
- [`SECURITY.md`](SECURITY.md) — what to do about a finding in this tool itself
- [`CHANGELOG.md`](CHANGELOG.md) — what changed, and when
- [`tests/specimens/README.md`](tests/specimens/README.md) — the specimens, what
  each proves, and the gaps that are named rather than hidden
- the sibling project's design notes — the design language this report follows

## License

Apache License 2.0.

---

<div align="center">

**Unmasker**

*What a human sees in a document, against what a machine reads out of it.*

Made by [osint-shifu](https://github.com/osint-shifu)

</div>
