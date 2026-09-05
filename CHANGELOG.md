# Changelog

Notable changes to `unmasker`, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`--json` carries its own `schema` field, which is versioned separately from the
release: `unmasker.scan/1` for one file, `unmasker.survey/1` for a folder. A
consumer should read that rather than the release number, because the release
moves whenever anything does and the schema moves only when the shape changes.

## [0.3.1] - 2026-09-05

### Fixed

- `invisible-text` was described as "text that the page's rendering
  instructions do not paint". True of a PDF render mode that paints neither
  fill nor stroke, and meaningless about a Word run marked hidden, which has
  produced the same finding since 0.3.0. The row now names both mechanisms.

  This is the second time a detector has gained a container and kept a
  description written for the first: `revision-history` was worded for the PDF
  Info dictionary until an XMP packet in a JPEG produced it, which is why
  `Metadata.container` exists.

  An invariant was written for it and then removed, because it did not catch
  what it was written for: the stale wording named *no* container rather than
  the wrong one, and a rule that a multi-container detector must not name
  exactly one passed it. Of the four detectors emitted from more than one
  module, only `invisible-text` has two container-specific ones; the rest pair
  a container with a module that serves several. Whether a description is
  *true* of every container that produces it is prose, and this one is read by
  hand at each release rather than guarded by a test that overstates itself.

## [0.3.0] - 2026-09-05

A minor version because a `.doc` is now read for its text rather than only for
what it says about itself, and because that unlocks every text detector on a
format where none of them ran. The runtime dependency count is unchanged, and
stays one: the piece table, the property tables and the compound file under
them are all read here.

### Added

- **A `.doc`'s text, story by story.** A Word document lays its body, its
  footnotes, its headers and footers, its comments, its endnotes and its text
  boxes end to end in a single character-position space, and the header says
  how long each part is. In the corpus specimen the body is 267 characters of
  504: a reader that took the main story and stopped would search just over
  half the file and then report having searched it, and the half it skipped
  holds a comment naming a bidder and a header marked *internal circulation
  only*. The report names which stories were searched.

- **Comments, with the name the file puts on each one.** The text is in the
  annotation story, the names are in a table of their own, and a third table
  says which name goes with which comment. Same finding and same detector name
  as a DOCX comment or a PDF annotation, arriving from a different container.

- **Tracked changes**, with the author and the date of each. A deleted
  sentence is `deleted-text`, the same finding a DOCX deletion makes.

- **Text carrying Word's hidden attribute**, as `invisible-text` — the name a
  PDF render mode that paints neither fill nor stroke already produces. The
  statement is identical: these characters are in the file and not on the page.

- **Field instructions.** A hyperlink is stored as an instruction, a separator
  and a result; the page shows the result. The instructions that name a
  location are quoted in a remark, in full. They are not findings: every table
  of contents and page number in every document is a field, and a detector
  that fired on all of them would say nothing.

- Three specimens and a builder for each: a document whose text is mostly
  outside the main story, one carrying a tracked deletion and a hidden run,
  and an Excel 97 workbook.

### Fixed

- **A deletion and a hidden run were being reported as text on the page.** A
  .doc keeps both in the piece table beside the printed text, and nothing in
  the characters says which is which — that is a `Chpx`, in a 512-byte page,
  addressed by byte offset while everything else counts characters. Reading
  the piece table alone would have had this tool announce a deleted sentence
  as visible prose, and Word's hidden text as ordinary body text, which is the
  exact statement it exists to contradict. Found by building a specimen with
  tracked changes and looking at what came out, not by a failing test.

- The remark saying a legacy file's text was not read covered `.doc`, `.xls`
  and `.ppt` at once. It now names the format, and the corpus holds a `.xls`
  so that the claim cannot be loosened to keep passing once the format beside
  it became readable.

### Notes

`0x0800` is the delete mark and `0x0801` the insert, which is the opposite of
what was written down from memory before the bytes were dumped. Guessing that
pair the wrong way round produces a tool that takes insertions off the page
*and* reports deletions as visible text — wrong in both directions, and green
against any fixture built from the same wrong memory. Every structure this
release reads was measured against a real file first, and two others corrected
a specification recalled wrongly: `GrpXstAtnOwners` has no header at all, and
LibreOffice writes `nFib` 257 rather than the 193 a Word 97 reader might check
for.

## [0.2.1] - 2026-09-05

### Fixed

- The landing screen still listed eight formats. `.doc`, `.xls` and `.ppt` had
  been readable since 0.2.0 and the README said so, but the first screen a
  reader sees did not - the tool contradicting its own front page, found by
  auditing the prose rather than by anything failing.
- The README credited six producers for the specimen corpus. Poppler and pypdf
  have written specimens since, and were not named.

### Added

- Two invariants for the claims that had drifted, both anchored to the corpus
  rather than to another document:

  A format with specimens must be named on the landing screen. A directory of
  specimens exists because a format is read and tested, so one the screen does
  not mention is a claim the tool is making too quietly.

  Every specimen must have a provenance note. The README says each does; a
  specimen without one is a file whose producer and contents are known to
  whoever added it and to nobody else, which makes it a fixture, and fixtures
  are what this corpus exists instead of.

## [0.2.0] - 2026-09-05

A minor version because a whole family of file formats is readable that was
not. The runtime dependency count is unchanged, and stays one.

### Added

- **Compound files.** `.doc`, `.xls` and `.ppt` are each a FAT filesystem in a
  single file, with a second smaller filesystem nested inside for streams below
  a cutoff. Nothing in the standard library reads one, so `unmasker.ole2` does:
  header, DIFAT, FAT, directory tree, mini FAT and mini stream, every chain
  cycle-checked and every offset bounds-checked, because this reads files
  somebody else wrote and some of them are wrong on purpose.
- **Property sets.** Both streams every Office application has written since
  1997 - title, author, company, keywords, revision count, timestamps -
  including the user-defined section, whose names are not numbers but entries
  in a dictionary the file carries.
- A specimen, and a Word 97 document is now dispatched by its signature.

### Three things that came from a real file rather than the specification

- **Every stream in an ordinary Word document is under the 4096-byte cutoff**,
  so all of them live in the mini stream. A reader that did full sectors first
  and left the small ones for later would read *nothing at all* from a genuine
  file while passing a suite built the same way it was. That is the HEIC
  failure exactly, and the specimen was read before the reader was written for
  precisely that reason.
- **The code page is declared by the file**, in property 1, and LibreOffice
  writes 65001. Assuming the specification's usual CP1252 is right for ASCII
  and wrong for every name with a diacritic in it.
- **Company is not property 15 of DocumentSummaryInformation.** LibreOffice
  writes it into a second section under `FMTID_UserDefinedProperties`. A reader
  built to the specification finds nothing there.

### The text is not read, and the report says so

The binary formats inside - Word's piece table, Excel's BIFF records - are each
a separate problem of their own size and none is solved here.

- `Extraction` gained `text_unread`: this file has a text layer that was not
  read, which is not the same as having none. A photograph has no text, so a
  metadata value genuinely appears nowhere in it; a `.doc` has text nobody
  looked at.
- `undisclosed-metadata` is therefore not run on one. Every field is absent
  from a text that was never read, and reporting six findings saying the
  document does not show values nobody asked it about would be the tool
  claiming a gap it did not look for.
- What the file says about itself is put in front of the reader as a remark
  instead, qualified as not compared. A value this tool read and mentioned to
  nobody would be the worst of both answers.
- The report's closing line says *this file's text was not read, so it was not
  searched*, rather than borrowing the sentence written for a photograph.

## [0.1.12] - 2026-09-05

### Fixed

- `--json` dropped `location.inside`. The terminal report said
  `in oleObject1.xlsx` and the JSON said nothing, so a pipeline could not tell
  a hidden sheet in the document from one in a workbook the document carries -
  the exact distinction the field was added for, missing from the consumer that
  most needed it. Found by running the published build rather than the tests,
  which all passed.

  `SCHEMA` stays at 1: the key is omitted when empty, like every other
  coordinate, and adding one a consumer may ignore does not change the shape.

## [0.1.11] - 2026-09-05

### Added

- A carried office package is now read as a document in its own right. A
  spreadsheet inside a report hides a sheet exactly as one on disk does, and
  the file somebody was sent is the one carrying it. `hidden-sheet`,
  `hidden-rows`, `filtered-rows` and everything else the spreadsheet reader
  knows now fire inside an embedded workbook.
- `Location` gained `inside`, so a finding says which carried object it came
  out of. A hidden sheet in the document and a hidden sheet in a workbook the
  document carries are not the same statement, and the report shows
  `in oleObject1.xlsx` where the second is meant.

### Notes

- Saying an object is there and saying what is in it are two findings. Both are
  reported; neither suppresses the other.
- One level only. A package inside a package is not descended into, because a
  document carrying itself would otherwise be read forever.
- Bytes are held for carried zips under 32 MB and dropped otherwise. Reading an
  embedded video into memory to discover it is a video costs more than the
  answer is worth.

### Known gaps

- OpenDocument embedded objects are not descended into. `Object 1/` is a
  directory of members rather than a file, and reassembling one into a package
  would mean this repository writing the document it then reads. The ODT
  specimen is reported as carrying an object and left at that.

## [0.1.10] - 2026-09-05

### Changed

- Two things this tool does not check are now named where their absence would
  otherwise pass for coverage.

  **Signature coverage.** A signed PDF's `/ByteRange` says which bytes it
  covers, and a file longer than that range has been appended to since it was
  signed - the natural companion to `earlier-revision` and entirely
  deterministic. No detector is written, because nothing available can produce
  a signed specimen: `pdfsig` only verifies, pypdf does not sign, and
  LibreOffice needs a certificate database this machine has no tooling to
  build. A detector whose only fixture came from the specification is the
  mistake the specimen corpus exists to prevent.

  **Font anachronism.** A typeface has a first release, so a document dating
  itself before a font it uses states two things that cannot both be true. Not
  implemented on purpose: the anchors worth having are Calibri, Aptos and
  DengXian, none installed here, so every testable case would be one nobody
  backdates a document with - a table that fires on real files while every
  tested case is irrelevant, which is worse than silence because it can be
  confidently wrong.

## [0.1.9] - 2026-09-05

### Added

- `earlier-revision`, the twenty-seventh detector, and the cleanest failed
  redaction there is. A PDF is appended to rather than rewritten: an edit
  leaves the original bytes where they are and writes a new cross-reference
  section after them. Delete a page that way and the page does not go
  anywhere - the new catalogue stops pointing at it, every viewer stops drawing
  it, and the text is untouched. It was invisible to this tool, which read what
  the current catalogue pointed at, like most tools do.

  Reported per revision rather than merged, because two edits are two decisions
  about what to stop showing and merging them would rank one against the other.
  What is quoted is the text, not the count: a number of revisions is trivia.

- A specimen: a one-page award notice whose earlier revision still holds the
  annex that was deleted, reserve price and name included.

### Notes on how it is read

- Revision boundaries are found in the raw bytes and then **proved by
  parsing**: `%%EOF` occurs inside streams, so an offset is a candidate until
  the bytes before it parse as a complete document on their own. Slower than
  trusting the marker, and close to impossible to fool.
- Eight boundaries are examined. A file with more says so in a remark rather
  than having the rest pass for searched.
- The specimen's update is written by pypdf, which is also this project's
  parser. It is checked against `qpdf`, an independent implementation, and the
  detector never asks pypdf where a revision begins.

## [0.1.8] - 2026-09-05

### Added

- `attached-file` now reads office packages as well as PDFs: OOXML objects
  under `*/embeddings/`, and OpenDocument's `Object N/` sub-packages, which are
  gathered into one finding each rather than reported a member at a time.
- Two specimens, both LibreOffice Writer: a summary paragraph disclosing no
  figures, with the workbook behind the pictured table carried in the package.

### Changed

- The finding says something different for an embedded object than for a PDF
  attachment, because the two are not the same claim. An attachment is on no
  page. An embedded object *is* on the page - what is on the page is a
  rendering of it - and reporting that as hidden would overstate it.
- Where the content is not text, the report says what the bytes are rather than
  leaving the column empty. "Nothing in the file" was printed beside a sentence
  saying the document carried 5454 bytes, which is the tool contradicting
  itself inside one finding. The kind is read from the first bytes, not from
  the name.
- A finding no longer names the same location twice. `"Object 1/" in Object 1/`
  teaches a reader that the second half of a sentence carries nothing.

### Known gaps

- What an embedded workbook holds is not read. A spreadsheet inside a document
  can carry hidden sheets and filtered rows exactly as one on disk can, and
  nothing descends into it yet.

## [0.1.7] - 2026-09-05

### Added

- `attached-file`, the twenty-sixth detector: a whole file carried inside a
  PDF's `/Names/EmbeddedFiles`. It is on no page, no viewer shows it unless
  asked, and printing the document does not print it - the same statement every
  other detector here makes, that the page and the file disagree about what is
  in this document. Text attachments are quoted; binary ones are named and
  measured, because quoting a workbook's bytes would be noise dressed as
  evidence.

  It is deliberately not called a hiding technique. An attachment is a feature
  used constantly and on purpose, so the finding says where the bytes are and
  stops. A reader decides what that means.
- A specimen: a LibreOffice decision notice naming no figure, with poppler's
  `pdfattach` carrying a note that gives the reserve price. The control is an
  existing PDF from the same producer with no attachment.

## [0.1.6] - 2026-09-05

### Added

- Every single-file report names the sha256 of the bytes it read, in the
  terminal, in `--html`, in `--md` and as a `sha256` field in `--json`. A path
  says where a report was made; it does not say what was in the file, and the
  person a report is forwarded to had no way to tell whether the document in
  front of them was the one it describes. The digest is printed whole - a
  shortened one checks nothing.

  Computed once, in the dispatch every reader goes through, so a format added
  later cannot arrive without it. A folder survey does not carry digests yet.

## [0.1.5] - 2026-09-05

### Added

- XMP is read from JPEG. The packet is the same one a PDF carries and the
  parsing was already a separate module; only one container was being handed
  to it. What an editor writes there is usually `xmpMM:History` - what the file
  was derived from, which application touched it, and when - and none of it is
  on the picture. `unmasker` reported a photograph's preview and nothing else
  until now.
- Two specimens for it, written by exiftool: one carrying an edit history, and
  a control carrying no packet at all, so the reader has a file it must stay
  silent on.

### Fixed

- The revision-history finding told every file its history "survives a scrub of
  the Info dictionary". A JPEG has no Info dictionary, and naming a structure
  the file does not have is a claim about nothing. Metadata now records which
  container it was read from and the sentence follows it.

## [0.1.4] - 2026-09-05

### Changed

- `low_contrast_text` no longer carries a guard that could drop a span without
  saying so. Narrowing the optional colours for the type checker had left a
  branch that skipped a span when a measurement was missing, and while that
  branch was unreachable - `flags` is only true where a measurement exists,
  and a span is nothing but a run of true flags - the wrong half of it was
  chosen. The code it replaced would have raised; this went quiet, and a
  finding that disappears without a trace is precisely the confusion between
  *searched and not there* and *there was nothing to search* that the rest of
  the tool works to prevent.

  The difference is now carried together with the two colours it was measured
  between, so the span reads all three without a guard and there is nothing
  left to drop. No output changes: the branch never ran.

### Added

- A specimen-free test for a line half-covered by an image, where the
  background is unreadable for some glyphs and known for the rest. It pins the
  invariant the detector now depends on structurally.

## [0.1.3] - 2026-09-05

### Fixed

- `LICENSE` held a reflowed copy of the Apache License 2.0, about 4.4 KB short
  of the canonical text and cut off at `END OF TERMS AND CONDITIONS`, with no
  appendix. Automated licence detection could not match it, so GitHub reported
  the project's licence as undetermined while the README badge, the package
  metadata and the PyPI classifier all said Apache-2.0 - a claim on the surface
  that the bytes underneath did not support, which is the thing this tool
  exists to point out. Every wheel published so far carried the truncated file
  as well.

  Replaced with the canonical text, verified byte-for-byte against two
  independent sources. The previous file contained no wording that is not in
  it.

## [0.1.2] - 2026-09-05

Documentation only, again. The description is the same file on both surfaces
and it did not read the same on both.

### Fixed

- Two callouts used GitHub's alert syntax, which only GitHub renders. On PyPI
  they showed the literal text `[!IMPORTANT]` and `[!NOTE]` above an ordinary
  quote. Both now open with the sentence they were emphasising, which carries
  the weight on either renderer and says something a label restating its own
  kind does not.

### Added

- A test refusing GitHub-only alert syntax anywhere in the README, so the next
  one is caught before it reaches PyPI.
- `UNMASKER_REFRESH_README=1 pytest tests/test_readme_examples.py` rewrites the
  page's example blocks from the tool. Every release moves the version inside
  the JSON example, so regenerating them was going to be manual work on each
  one.

## [0.1.1] - 2026-09-05

Documentation only. The code published as 0.1.0 is the code published here;
the version moved because PyPI renders the description baked into the release
and had no other way to be shown the current front page.

### Changed

- The README's examples are output the tool actually produced, and a test now
  runs each command on the page and compares it to the block printed beneath
  it. They had drifted: one claimed four findings and listed two, for a file
  not in the repository; another showed two findings for a spreadsheet that
  yields seven; the JSON example carried a literal `"..."` inside an array,
  below the promise that values are never shortened with ellipses.
- The front page spells the project `unmasker`, the way the package always
  did. The description carried by 0.1.0 capitalised it in four places.

### Added

- A test tying `__version__` to the version in `pyproject.toml`. They are two
  claims about one fact kept in two files, and only the second was checked at
  release time, so `--version` could name a release the package metadata did
  not.

## [0.1.0] - 2026-09-05

First release.

### Added

- 25 detectors across seven groups: covered and under-image text, invisible and
  low-contrast text, off-page text; zero-width, bidi, tag and mixed-script
  characters; hidden sheets, rows, columns, filtered rows and tracked cell
  changes; hidden slides and speaker notes; stale EXIF thumbnails; tracked
  deletions, comments, revision history and metadata leaks; and — with `--ocr` —
  text that renders but does not extract, and text that extracts but does not
  render.
- Readers for PDF, DOCX, ODT, XLSX, ODS, PPTX, ODP, JPEG and plain text,
  dispatched by content rather than by extension.
- Folder surveys: point it at a directory and it reports which files to open
  next, without ranking them against each other.
- `--html` and `--md` reports, both escaping every value they quote, because
  everything quoted came out of a document somebody else wrote.
- `--json` for pipelines, with a `schema` field naming the shape and a
  `searched` field distinguishing *nothing was found* from *there was nothing to
  search*.
- Three exit statuses: `0` clean, `1` findings, `2` unreadable — because a file
  that could not be read is not a file that came back clean.
- `py.typed`, so the annotations are visible to anything importing `unmasker`
  as a library.

### Fixed

- `jpeg.dimensions()` walked past the start-of-scan marker and read a `0xFFC0`
  out of the entropy-coded data, reporting a picture the size of noise. It now
  stops at `SOS`/`EOI` the way `_segments()` already did.

[0.2.1]: https://github.com/osint-shifu/unmasker/releases/tag/v0.2.1
[0.2.0]: https://github.com/osint-shifu/unmasker/releases/tag/v0.2.0
[0.1.12]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.12
[0.1.11]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.11
[0.1.10]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.10
[0.1.9]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.9
[0.1.8]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.8
[0.1.7]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.7
[0.1.6]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.6
[0.1.5]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.5
[0.1.4]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.4
[0.1.3]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.3
[0.1.2]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.2
[0.1.1]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.1
[0.1.0]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.0
