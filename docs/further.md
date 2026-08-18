## Usage

Run the workflow as usual, then ask for the report:

```bash
snakemake --cores 4
snakemake --reporter fairscape
```

That writes `ro-crate-metadata.json` into the working directory, followed by
the derived artifacts:

* `ro-crate-datasheet.html` and `ai_ready_score.json` — human-readable
  datasheet and AI-Ready score
* `ro-crate-prov-graph.json` / `.html` — the evidence graph and an interactive
  visualization of it
* `ro-crate-linkml.yaml` — the LinkML/D4D (Datasheets for Datasets) export

Those three are on by default and read only the crate JSON. They are produced
by fairscape-cli 1.2.10 or newer; with an older fairscape-cli — or none at all —
the crate is still written and the steps after it are skipped with a note.

Everything that touches the data files themselves is opt-in:

```bash
# infer an EVI Schema per data file (csv/tsv/parquet/h5/hdf5/hea/dcm)
snakemake --reporter fairscape --report-fairscape-schemas

# describe every file inside a directory() output, not just the directory
snakemake --reporter fairscape --report-fairscape-expand-directories

# SHA-256 Merkle tree over the crate's files
snakemake --reporter fairscape --report-fairscape-merkle
```

Crate-level metadata is worth setting once you publish a crate:

```bash
snakemake --reporter fairscape \
  --report-fairscape-name "RNA-seq differential expression" \
  --report-fairscape-description "Salmon quantification and DESeq2 analysis of the pilot cohort" \
  --report-fairscape-author "Jane Doe" \
  --report-fairscape-keywords "rna-seq,deseq2,pilot" \
  --report-fairscape-license "https://spdx.org/licenses/CC-BY-4.0"
```

## What ends up in the crate

* **A run Computation** for the workflow as a whole: `usedDataset` is the set
  of root inputs no job produced, `generated` the set of terminal outputs no
  job consumed, and its start/end times are the earliest and latest job times.
* **One Computation per executed job**, carrying the resolved shell command,
  the rule's `params`, its inputs (from the persistence metadata) and its
  declared outputs, with wildcards resolved into the job's name.
* **Software entities** for the Snakefile, the Snakemake engine (versioned),
  and every rule. A rule's Software points at the file that actually defines
  its action: the `.py`/`.R` file for a `script:` rule, the notebook for
  `notebook:`, the resolved wrapper URL for `wrapper:`, and the Snakefile for
  `shell:`/`run:` rules. Container images and conda environments are recorded
  when declared.
* **One Dataset per unique file** — inputs, outputs, intermediates and
  configfiles. Files inside the crate directory get a crate-relative
  `contentUrl`; files outside it, or already deleted (`temp()` intermediates),
  get a `localPath` instead, since a relative `contentUrl` is a promise the
  bytes are there.

Both directions of every provenance edge are written (`generated` and
`generatedBy`), so the graph can be walked from either end.

## Which files are captured

Every declared output of every executed job, plus every input recorded in the
persistence metadata, plus configfiles. Nothing needs to be marked with
`report(...)` — that channel only feeds Snakemake's own HTML reporter, and this
plugin ignores it in favour of the full job list.

Not captured: files a rule writes without declaring them in `output:`
(Snakemake has no record of them either), `benchmark:` files, and jobs that
failed or never ran — a failed job leaves no persistence metadata, so only
successful work is described.

## Caveats of the post-hoc design

The reporter reconstructs the run from `.snakemake/metadata` after the fact.
That is what makes it free of runtime risk, but it also means:

* the run Computation's `command` is literally `snakemake` — the original
  command line is not part of the metadata the report step can see;
* re-running the same workflow overwrites the persistence metadata, so the
  crate always describes the most recent run;
* `temp()` intermediates are described with full provenance edges but without
  `contentSize`, since the bytes are gone by report time;
* the Snakefile must still parse at report time.

## Relationship to the rest of FAIRSCAPE

This package owns the Snakemake side only: it reduces the report interface,
the persistence metadata and the filesystem state to a plain-data records
document. The Snakefile-to-EVI mapping and the ARK minting live in
[fairscape_conversion](https://github.com/fairscape/fairscape_conversion)
(`plugins/snakemake`), shared with the Nextflow, Cromwell, MLflow, WRROC and
C2M2 converters; the datasheet, evidence graph, LinkML export and schema
inference are [fairscape-cli](https://github.com/fairscape/fairscape-cli)'s own
functions, called directly rather than reimplemented.

Setting `SNAKEMAKE_FAIRSCAPE_DUMP_RECORDS=<path>` on a report run dumps the
records document that crosses that boundary, which is the fastest way to see
what the plugin extracted.

Full documentation, including the exact provenance semantics and the list of
undeclared Snakemake interfaces the plugin depends on, is in the
[repository README](https://github.com/fairscape/snakemake-report-plugin-fairscape#readme).
