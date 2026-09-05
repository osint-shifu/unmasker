# `exiftool-xmp-history.jpg`

**Producer:** ImageMagick 6.9 (`convert`) for the picture, exiftool 12.x for the
packet. Built by
[`sources/build_xmp_in_a_photograph.py`](../sources/build_xmp_in_a_photograph.py).

## What a person sees

A flat blue-grey panel, 400 x 300, with the word `PRZYKLAD` on it in white.
Nothing else. It is a picture, and a picture says nothing about itself.

## What is stored inside

An XMP packet in its own APP1 segment, holding an edit history:

| | |
| :--- | :--- |
| `xmpMM:DerivedFrom/documentID` | `xmp.did:8f1c2a6b-nie-istnieje` |
| history event 1 | `derived` by Adobe Photoshop 25.0 (Windows), 2026-02-11T09:14:00+01:00, touching `/metadata` |
| history event 2 | `saved` by Adobe Photoshop 25.0 (Windows), 2026-02-11T09:31:00+01:00 |

## Why this file exists

`tests/specimens/README.md` named **XMP outside a PDF** as a gap, and named it
correctly: the packet is the same in a photograph as in a document, and only
one container was being read. This file closes that half.

What it demonstrates is not another field dump. An editor writes
`xmpMM:History` as a matter of course, it survives every subsequent save, and
it records **what this file came from** — a document identifier for a file the
picture gives no other sign of. A person looking at the image cannot tell it
was derived from anything.

The software agent names an application that never touched this file, the
document it claims to derive from does not exist, and the dates are invented.
The packet is written by exiftool rather than assembled here, because a packet
built to match the specification proves nothing about the packets real editors
write — which is the lesson `filetrail`'s HEIC reader paid for.

## The control

[`exiftool-xmp-absent.jpg`](exiftool-xmp-absent.md) is the same picture with no
packet at all. Without it this file shows a reader firing, not a reader being
right, and a reader that fires on every photograph is worse than none.
