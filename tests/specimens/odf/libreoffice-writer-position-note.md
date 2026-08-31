# libreoffice-writer-position-note.odt

Six kinds of hidden thing in one file, and the file type `unmasker` used to
refuse outright.

- 13 034 bytes, `sha256:7eaf90ed9fda3e44…`
- written by LibreOffice 24.2 in its **own** format

## How it was made

```bash
python3 tests/specimens/sources/build_odf_document.py \
    tests/specimens/odf/libreoffice-writer-position-note.odt
```

Flat ODF converted to `.odt`, which is the same format zipped. This is the only
specimen here that does not depend on the fidelity of an export filter —
LibreOffice is writing what it natively writes, so the question every other
specimen has had to answer ("does this survive the conversion?") does not
arise.

## What a human sees

```text
POSITION NOTE - DRAFT                       ← running header

POSITION NOTE - SYNTHETIC

The figure is withheld pending advice. It is now a figure to be settled.
The panel meets again in June.

Queries to h.probna@example.org in the first instance.
```

## What is actually in the file

| | |
| --- | --- |
| `<text:deletion>` | `the earlier estimate of 3.1 million`, by Halina Probna-Test, 2024-05-06 |
| `<office:annotation>` | `Do not share the working file with the other side.` |
| `meta:initial-creator` | `Halina Probna-Test` |
| `dc:title` | `Position note - internal only` |
| `meta:user-defined name="Client"` | `Meridian Trust BV` |
| a zero-width space | inside `h.probna@example.org` |

Six findings, in five kinds, from one document.

## The care ODF needs that OOXML does not

**Both of the things that must not be read as body text live inside the body.**
`<text:tracked-changes>` sits at the top of `office:text` and holds every
deleted passage; `<office:annotation>` sits inline in its own paragraph.
Extracting the body naively reports the struck-out sentence and the private
comment as ordinary visible prose — which is exactly backwards, since a reader
of the page sees neither.

In OOXML both live in separate parts of the zip and the mistake is harder to
make.

## What mutation testing added to this file

The first version of it had a deletion, a comment, metadata and a zero-width
space, and four mutations survived against it. Every one said the same thing:
*the specimen is too thin.* So it gained

- **a tracked insertion**, because nothing otherwise distinguished the two
  kinds of region — and an insertion is on the page, so it must be body text
  and never a finding;
- **a running header**, because nothing otherwise said `styles.xml` was read at
  all, and a document reported as holding nothing because only `content.xml`
  was checked has been told something untrue;
- **a comment mid-sentence** with words after it, because skipping a subtree
  must not swallow what follows it on the line and a comment at the end of a
  paragraph never tests that;
- **a custom property**, because ODF's `meta:user-defined` gets the same
  treatment as OOXML's custom properties and nothing exercised it.

Enriching the specimen was the right answer to all four. Four synthetic tests
would have passed just as well and proved considerably less.

## One correction it forced

`revision-history` used to end *"A name here is whatever the copy of Word was
configured to say."* On a file LibreOffice wrote in its own format that is
simply untrue, and the sentence now names the application that wrote the file
rather than one particular product.
