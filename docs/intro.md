This plugin turns a completed Snakemake run into a
[FAIRSCAPE](https://fairscape.github.io/) EVI RO-Crate: an
`ro-crate-metadata.json` describing the run as a provenance graph — one
Computation per executed job (with its resolved shell command, parameters,
inputs and outputs), one Software per rule plus the Snakefile and the Snakemake
engine itself, and one Dataset per file the workflow read or wrote. Alongside
the crate it generates the FAIRSCAPE artifact set: a human-readable datasheet,
an AI-Ready score, an interactive evidence graph, a LinkML/D4D export, and —
on request — an inferred schema for every tabular or array data file.

Nothing in your workflow has to change, and no file needs to be flagged with
`report(...)`: the plugin reads Snakemake's own per-job persistence metadata
plus the report interface's job records, so every declared output of every
executed job is described, intermediates included.

The report step is post-hoc — it runs as a separate `snakemake --reporter
fairscape` invocation against `.snakemake/metadata`, so it adds no runtime
overhead, cannot fail a run, and works on runs that finished before the plugin
was installed.

Identifiers are deterministic ARKs hashed from run-independent strings
(Snakefile path, rule name, rule plus sorted outputs, file path), so
re-generating the report — or re-executing the whole workflow with `--forceall`
— reproduces byte-identical identifiers.

Install the plugin together with its artifact generator:

```bash
pip install 'snakemake-report-plugin-fairscape[artifacts]'
```

The `[artifacts]` extra pulls in `fairscape-cli`, which produces everything
downstream of the crate. Without it the crate itself is still written and those
steps are skipped with a note.
