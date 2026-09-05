# libreoffice-impress-hidden-slide.odp

The same board review as
[`pptx/libreoffice-impress-hidden-slide.pptx`](../pptx/libreoffice-impress-hidden-slide.md),
in LibreOffice's own format.

- 16 049 bytes
- produced by LibreOffice 24.2 Impress

## What is actually in the file

```xml
<draw:page draw:name="Cut" draw:style-name="dp3">
...
<style:style style:name="dp3" style:family="drawing-page">
  <style:drawing-page-properties presentation:visibility="hidden"/>
```

and, inside slide 1:

```xml
<presentation:notes>
  <draw:frame><draw:text-box><text:p>Do not give the headcount number…
```

## What it is for

**A slide's visibility is behind an indirection, exactly as a sheet's is.**
The page carries a style name; the style, elsewhere in the file, says
`presentation:visibility="hidden"`. A reader looking for an attribute on the
page finds nothing and reports a deck with a cut slide as clean.

This is the second time this format has done it — `libreoffice-calc-hidden-columns.ods`
hides a whole sheet the same way — and having met it once is the only reason it
was expected here rather than discovered by a bug report. The two readers are
separate because of it: OOXML puts the fact on the thing, ODF puts it behind a
name.

**Notes sit inside the slide they belong to.** `<presentation:notes>` is a
subtree of `<draw:page>`, which is the same shape as an annotation inside a
paragraph and carries the same trap: walking the page naively puts the
speaker's private line into the text of the slide itself, where the character
detectors would search it as though an audience had seen it.

`readers/odf.py` documents that trap for annotations and
`odf/sheets.py` for cell comments. This is its third appearance in the same
format.

## What this specimen does not carry

- **A master-page note**, which is boilerplate rather than a speaker's own.
- **`presentation:visibility` on anything but a page.**
- **A deck with no slides at all**, which is covered synthetically.
