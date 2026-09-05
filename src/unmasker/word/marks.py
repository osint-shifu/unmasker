"""The format's own punctuation, and what a person sees in its place.

These bytes are structure, exactly as a `<w:p>` tag is structure in a .docx.
A table cell ends with `0x07`; a footnote reference is `0x02`; a comment
anchor is `0x05`. None of them is content, and reporting one as an invisible
character would be this tool inventing a finding out of the file format.

Anything **not** named here is left where it is, so a control character that
is not part of the format still reaches the detectors that look for one. The
list is what is known to be punctuation, not everything that happens to be
unprintable - those are different claims, and the second one is not true.
"""

from __future__ import annotations

PUNCTUATION = {
    "\r": "\n",      # end of paragraph
    "\x07": "\n",    # end of a table cell, and again for the row
    "\x0b": "\n",    # line break inside a paragraph
    "\x0c": "\n",    # page break
    "\x1e": "-",     # non-breaking hyphen
    "\x1f": "",      # optional hyphen, shown only where the line wraps
    "\x01": "",      # a picture or an embedded object sits here
    "\x02": "",      # a footnote or annotation reference mark
    "\x05": "",      # a comment anchor
    "\x08": "",      # a drawn object sits here
    "\x00": "",
}


def readable(text: str) -> str:
    """The punctuation replaced by what the page shows in its place."""
    return "".join(PUNCTUATION.get(character, character) for character in text)


__all__ = ["PUNCTUATION", "readable"]
