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

> **Status: tier 2 works. Tier 1 does not exist yet.**
>
> `unmasker` finds invisible characters today - zero-width characters, bidi
> overrides, plane-14 tag characters and mixed-script words - in PDF, DOCX and
> any text file. The rectangle-over-text detector, which is the one in the
> example above, is not built. A clean run means the detectors that exist found
> nothing, and the report says exactly that rather than calling the document
> clean.
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
