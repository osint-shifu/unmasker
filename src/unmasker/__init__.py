"""What a human sees in a document, against what a machine reads out of it."""

__version__ = "0.1.7"

#: The shape of `--json`, which is not the same question as the build that
#: wrote it. `version` moves at every release and tells a consumer nothing
#: about whether its parser still works; this moves only when a field is
#: removed or given a new meaning. Emitted as `unmasker.<shape>/<SCHEMA>` -
#: `scan` for one file, `survey` for a folder, because those are two
#: different documents and nothing else told them apart.
SCHEMA = 1
