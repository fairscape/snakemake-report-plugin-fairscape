# snakemake-report-plugin-fairscape

[![PyPI](https://img.shields.io/pypi/v/snakemake-report-plugin-fairscape)](https://pypi.org/project/snakemake-report-plugin-fairscape/)
[![CI](https://github.com/fairscape/snakemake-report-plugin-fairscape/actions/workflows/ci.yml/badge.svg)](https://github.com/fairscape/snakemake-report-plugin-fairscape/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Turns a finished Snakemake run into an **RO-Crate**: one
`ro-crate-metadata.json` recording what ran, what it read and wrote, and how
each output was produced — plus a readable datasheet and an interactive
provenance graph. It's a publishable, archivable record of the run, following
the [FAIRSCAPE](https://fairscape.github.io/) EVI provenance model.

Your workflow doesn't change. Run Snakemake as usual, then ask for the report:

```bash
pip install 'snakemake-report-plugin-fairscape[artifacts]'

snakemake --cores 4             # your run, unchanged
snakemake --reporter fairscape  # writes the crate + artifacts
```

## What you get

| File | What |
| ---- | ---- |
| `ro-crate-metadata.json` | the provenance graph: one entry per job, rule, and file, with the edges between them |
| `ro-crate-datasheet.html` + `ai_ready_score.json` | human-readable summary and an AI-readiness score |
| `ro-crate-prov-graph.json` / `.html` | evidence graph + interactive viewer |
| `ro-crate-linkml.yaml` | LinkML / Datasheets-for-Datasets export |

Everything after the crate comes from `fairscape-cli` (the `[artifacts]` extra,
1.2.10+). Without it the crate is still written and the rest is skipped with a
note.

## Options

All optional, all prefixed `--report-fairscape-`:

| Flag | Default | Effect |
| ---- | ------- | ------ |
| `path` | `ro-crate-metadata.json` | where to write the crate |
| `name` / `description` | from the Snakefile | crate title and blurb (description ≥ 10 chars) |
| `author` | current user | author on the crate and its entities |
| `keywords` | `snakemake,workflow` | comma-separated |
| `license` | CC-BY-4.0 | license URL |
| `version` | `1.0` | crate version |
| `naan` | `59853` | ARK Name Assigning Authority Number |
| `schemas` | off | infer a column schema per data file (csv/tsv/parquet/h5/hdf5/hea/dcm — reads the data) |
| `expand-directories` | off | describe each file inside a `directory()` output, not just the directory |
| `expand-max-files` | `1000` | cap per expanded directory |
| `merkle` | off | SHA-256 Merkle tree (reads every file) |
| `preview` | off | also write `ro-crate-preview.html` |
| `croissant` | off | also write a Croissant JSON-LD export |
| `no-datasheet` / `no-evidence-graph` / `no-linkml` / `no-link-inverses` | on | skip that step |

Anything that reads your data files is opt-in; the defaults only read the crate
JSON.

```bash
snakemake --reporter fairscape \
  --report-fairscape-name "RNA-seq differential expression" \
  --report-fairscape-author "Jane Doe" \
  --report-fairscape-schemas
```

## Snakemake specifics

- **Nothing needs `report(...)`.** The plugin reads the full job list, not the
  `report()` channel, so every declared output of every executed job is
  captured, intermediates included.
- **Post-hoc.** It reconstructs the run from `.snakemake/metadata` after the
  fact, so it adds no runtime overhead, can't fail a run, and works on runs
  that finished before it was installed. The Snakefile must still parse.
- **Only successful jobs.** A failed or never-run job leaves no persistence
  metadata and is absent from the crate.
- **Last run wins.** Re-running the workflow overwrites the metadata, so the
  crate describes the most recent run. The run's `command` is just `snakemake`
  — the original command line isn't recorded anywhere the report step can see.
- **Identifiers are stable.** ARKs hash only run-independent strings (Snakefile
  path, rule name, file path), so re-reporting — or re-running with
  `--forceall` — reproduces identical IDs.
- Tested against snakemake 9.25.1.

## Development

```bash
pip install '.[artifacts,validate]'    # NOT -e: see below
pip install snakemake
tools/run-examples.sh
```

**Install non-editable.** Snakemake discovers plugins with
`pkgutil.iter_modules`, which doesn't see editable installs — a `pip install -e .`
plugin is silently missing from `--reporter`. Re-run `pip install .` after each
change.

Releasing: [RELEASING.md](RELEASING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
