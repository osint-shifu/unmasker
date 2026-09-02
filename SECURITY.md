# Security

## What this tool is exposed to

`unmasker` exists to be pointed at documents nobody trusts. That is the whole
use case: a leaked PDF, a file from a counterparty, an attachment on its way
into a retrieval pipeline. It parses hostile input by design.

So the threat model is the parser, not the network:

- It makes **no network requests**, ever.
- It is **read-only**. It never writes to, moves or modifies the file it is
  given.
- It runs **locally**. Nothing is uploaded, and nothing phones home.
- It has **one runtime dependency**, `pypdf` — pure Python, BSD-3-Clause, with
  no transitive dependencies of its own.

`--ocr` is the exception worth knowing about: it shells out to `ghostscript`
and `tesseract` to render a page and read it back. Those are large C
codebases with their own history, they are **off unless you ask for them**,
and they run over a file you have already chosen to open.

## What counts as a vulnerability

- A crash, a hang, or unbounded memory or disk use on a malformed document.
  A forensic tool that dies on the one file that mattered has failed at its
  job, and a decompression bomb that fills a disk is a real finding here.
- Anything that escapes reading — a path written outside a temporary
  directory, a subprocess invoked with attacker-controlled arguments, code
  executed out of a document.
- A finding the tool states that the file does not support, or hidden content
  it silently fails to report. Both are correctness bugs and both are treated
  as security bugs, because people make decisions about disclosure on this
  output.

## Reporting

Please report privately first, through **GitHub Security Advisories** on this
repository (Security → Report a vulnerability). If that is not available to
you, open an issue saying only that you have something to report and asking
for a contact — do not put the details in a public issue.

Please include:

- what you ran and what happened
- the file, if you can share it — and if you cannot, which is normal in this
  line of work, a **builder script** that produces something with the same
  shape is just as useful and safer for everyone
- the version (`unmasker --version`) and platform

You will get an acknowledgement. This is a small project maintained in
whatever time there is, so a fix may take a while; you will be told where it
stands rather than left waiting.

## Handling documents

A note rather than a policy, because it has caught people out:

**Do not paste a real document into an issue.** The whole point of this tool
is that files carry more than they show, and an attachment on a public tracker
carries all of it — the metadata, the tracked changes, the hidden sheet. Use a
builder.

The specimens in this repository are all synthetic for the same reason. Every
particular in them is invented, and the e-mail domain is `example.org`, which
RFC 2606 reserves for the purpose.
