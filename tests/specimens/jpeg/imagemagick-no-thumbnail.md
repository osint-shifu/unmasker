# imagemagick-no-thumbnail.jpg

The second control, and the one that tests the *other* meaning of silence. The
same photograph as
[`imagemagick-stale-thumbnail.jpg`](imagemagick-stale-thumbnail.md) before it
was cropped and before any preview was written into it.

- 33310 bytes
- produced by ImageMagick, with no exiftool step at all

## What is in the file

| | |
| --- | --- |
| the picture | 800×600, aspect 1.33 |
| the preview in its EXIF | none - there is no thumbnail tag |

## What it proves

Most photographs on the web carry no preview, and their absence is not a
finding about anything. `stale-thumbnail` has to stay silent here.

It also has to stay silent *for the stated reason*. "Nothing found" has two
meanings and this file is the one where the second applies: there was nothing
to compare, rather than a comparison that came back clean. The reader is told
so in a remark, and `--json` carries it, because a reader who confuses the two
has drawn a conclusion this tool never supported.

## Why it is committed rather than built in the test

The test that needed a photograph without a preview originally shelled out to
`convert` to make one. No CI runner has ImageMagick, so the test failed on
Ubuntu and macOS with `FileNotFoundError` - and on Windows it found the NTFS
`convert` utility under the same name and failed with exit status 4.

`CONTRIBUTING.md` already names this failure once: every test that shells out
is guarded, and the first CI run failed because one of them was not. This is
the same lesson arriving a second time, and the answer is the one this project
already gives everywhere else - commit the specimen.
