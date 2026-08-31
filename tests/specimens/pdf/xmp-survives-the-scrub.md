# xmp-survives-the-scrub.pdf

The Info dictionary was cleaned. The XMP packet was not. Anybody who checks the
obvious place sees a tidy file; everything that was supposed to go is still in
the other half of it.

- 16 177 bytes, `sha256:c24d0b0e99f5e1a7…`
- page and Info dictionary by LibreOffice 24.2; XMP packet and scrub by
  exiftool 12.76

## How it was made

```bash
python3 tests/specimens/sources/build_xmp_survives_the_scrub.py \
    tests/specimens/pdf/xmp-survives-the-scrub.pdf
```

Three steps, in the order the failure actually happens. LibreOffice writes the
page and the original Info dictionary. exiftool writes the XMP packet. exiftool
then clears `/Author`, `/Subject` and `/Keywords` and rewrites `/Title` — and
touches nothing in the packet, because that is a separate operation nobody
thought to run.

**exiftool is the point of using exiftool.** It is the canonical XMP
implementation and has nothing to do with this project, so the packet is not
something written to suit the parser that will read it. LibreOffice writes no
XMP at all, which is why this is the only specimen needing a producer outside
the office suite.

## What a human sees

```text
The company will not be commenting further at this time.
```

## What the Info dictionary says

```text
/Title        Statement
/Creator      Writer
/Producer     LibreOffice 24.2
/CreationDate a timestamp
```

No author. No subject. No keywords. It looks like a file somebody cleaned.

## What is actually in the XMP packet

| property | value |
| --- | --- |
| `dc:creator` | `Halina Nowak-Test` |
| `dc:title` | `Statement - HOLD until legal clears` |
| `dc:description` | `Do not release before the settlement is signed.` |
| `Iptc4xmpCore:CreatorContactInfo/CiEmailWork` | `h.nowak@example.org` |
| `xmpMM:OriginalDocumentID` | the document this one was made from |
| `xmpMM:DerivedFrom/documentID` | a document this one was derived from |
| `xmpMM:History` | `saved` by `Acrobat Distiller 24.0 (Windows)`, 2024-04-19 |
| `xmp:CreatorTool` | `LibreOffice/24.2.7.2$Linux_X86_64` |

Nine findings from a file whose Info dictionary looks clean.

## The one that could not come from anywhere else

```text
● the Info dictionary gives Title as "Statement" and the XMP packet gives
  dc:title as "Statement - HOLD until legal clears"
```

A PDF states its metadata twice and nothing in the format makes the two agree.
That is not a defect in this specimen — it is the format, and it is why
"metadata removed" so often means "one of the two copies removed". No detector
that reads a single copy can see this at all.

## Details this specimen exists to hold

**`/Subject` maps onto `dc:description`, not `dc:subject`.** The PDF
specification says so; `dc:subject` corresponds to `/Keywords`. Pairing them by
name would compare two fields that mean different things and report a conflict
that is not one.

**`xmp:CreatorTool` is `LibreOffice/24.2.7.2$Linux_X86_64`.** The same dotted
quad as in `docProps/app.xml`, in a different container, and the same answer:
the field names a tool, so it is a version and it is a remark.

**`/Creator` and `xmp:CreatorTool` disagree here**, and neither is reported.
Both are true, both name a tool, and files say two different things about that
constantly — a PDF written by one application and distilled by another says
both truthfully. They are a listed pair precisely so that the rule suppressing
them is a rule and not an omission.

## What it does not carry

- **A packet written in attribute form**, which is how Adobe writes them. The
  parser handles it and only a synthetic test exercises it.
- **A multi-event history.** This one has a single event; two-event histories
  are covered synthetically.
- **XMP in anything but a PDF.** DOCX, JPEG and TIFF carry packets too, and
  nothing here reads them.
