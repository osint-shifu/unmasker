# Changelog

Notable changes to `unmasker`, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`--json` carries its own `schema` field, which is versioned separately from the
release: `unmasker.scan/1` for one file, `unmasker.survey/1` for a folder. A
consumer should read that rather than the release number, because the release
moves whenever anything does and the schema moves only when the shape changes.

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

[0.1.1]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.1
[0.1.0]: https://github.com/osint-shifu/unmasker/releases/tag/v0.1.0
