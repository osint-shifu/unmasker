# unmasker

**What a human sees in a document, against what a machine reads out of it.**

A black rectangle drawn over text is not a redaction. The text is still in the
file, and every parser can read it. The same gap covers text in the colour of its
background, text drawn with the invisible render mode, text positioned off the
page, zero-width and bidi characters, and tracked changes that keep deleted text
inside the document.

`unmasker` reports each place the two layers disagree, and says nothing beyond
what it can show.

```bash
unmasker leaked.pdf
```

> **Status: it does the thing on the tin.**
>
> Text under a filled shape, reported per character rather than per line, so a
> bar dragged too short is reported as covering exactly what it covers. Text
> drawn in a render mode that paints nothing, or at an opacity that paints
> nothing - `color: transparent` is one CSS declaration and changes no render
> mode at all. Zero-width characters, bidi
> overrides, plane-14 tag characters and mixed-script words, in PDF, DOCX and
> any text file.
>
> Text painted in the colour of what is behind it, whether that is a shape or
> the bare paper. Text positioned outside the visible page - which is the crop
> box, and a crop box smaller than the media box is how a "cropped" file keeps
> what was cropped off. Text under an image, reported separately because a scan
> of a printed page looks the same and usually agrees with itself.
>
> Comments: in a Word document, and in a PDF, where they are annotations
> hanging off the page rather than part of it and no text extraction reports
> them. In a Word document also: text a tracked deletion took off the page and
> left in the file, and one line naming who edited it and when.
>
> In the metadata of either: a name, a client, a codename or a path that the
> document's own text never shows. What produced the file and when stays a
> note, not a finding - every PDF has a producer, and a tool that failed every
> document on that would be no gate at all.
>
> And in a PDF's XMP packet, which is the *second* place it states its
> metadata: what a scrub of the Info dictionary left behind, the trail of
> applications that have touched the file, and every place the two halves
> disagree about what the file is.
>
> Not yet: OCR, and the containers `filetrail` reads that this does not. A
> clean run means the detectors that exist found nothing, and the report says
> that rather than calling the document clean.
>
> See [`HANDOFF.md`](HANDOFF.md) for what this is, what was decided and why, and
> what has been verified against real files.

## Why

The person redacting a document sees a black bar and believes the job is done.
It keeps happening in court filings and government releases, because the tool
that draws the bar does not remove what is under it.

The same detection serves two more uses. A PDF fed to a retrieval pipeline can
carry instructions a human reviewer will never see. And a leaked or altered
document can be checked: what did the tracked changes hold, does the text layer
agree with the image, what does the metadata say.

## Design

- **A reader, not a scanner.** It shows the evidence; you draw the conclusion.
- **Local and read-only.** No network, no service, no writes to inspected files.
- **One runtime dependency**, `pypdf`, and the reasoning for it is written down.
- **Never states what it cannot show.** No verdicts.

## License

Apache License 2.0.
