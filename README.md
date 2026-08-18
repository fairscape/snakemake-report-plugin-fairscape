# snakemake-report-plugin-fairscape

[![PyPI](https://img.shields.io/pypi/v/snakemake-report-plugin-fairscape)](https://pypi.org/project/snakemake-report-plugin-fairscape/)
[![CI](https://github.com/fairscape/snakemake-report-plugin-fairscape/actions/workflows/ci.yml/badge.svg)](https://github.com/fairscape/snakemake-report-plugin-fairscape/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

A Snakemake report plugin that turns a completed run into a
[FAIRSCAPE](https://fairscape.github.io/) EVI RO-Crate — `ro-crate-metadata.json`
describing every job, rule, and file of the run, plus the derived artifact set
(datasheet, AI-Ready score, evidence graph, LinkML/D4D export, inferred
schemas). No changes to your workflow: run Snakemake as usual, then ask for the
report.

```bash
pip install 'snakemake-report-plugin-fairscape[artifacts]'

cd your-workflow/
snakemake --cores 4             # run as usual
snakemake --reporter fairscape  # writes ro-crate-metadata.json + artifacts
```

The `[artifacts]` extra pulls in `fairscape-cli`, which generates everything
downstream of the crate. Without it the crate itself is still written and those
steps are skipped with a note.

## Where the code lives

This repository is the **Snakemake side only**. It reduces Snakemake's report
interface, persistence metadata, and filesystem state to a plain-data records
document, and hands that to the shared converter engine:

| Piece | Where |
| ----- | ----- |
| Snakemake extraction (report interface, `.snakemake/metadata`, file stats) | here |
| Snakefile → EVI mapping, deterministic ARK minting | [`fairscape_conversion`](https://github.com/fairscape/fairscape_conversion), `plugins/snakemake` |
| Datasheet, evidence graph, LinkML export, schema inference | [`fairscape-cli`](https://github.com/fairscape/fairscape-cli) |

Nothing downstream of the crate is reimplemented here — the reporter calls
`fairscape_cli.utils.build_utils.process_crate` and
`fairscape_cli.models.schema.infer_schema` directly, so parity with the CLI is
by construction rather than by test suite. The mapping in
`fairscape_conversion` is CSV-driven and pinned by a golden-file test built
from this repo's `letters-chain` example.

Set `SNAKEMAKE_FAIRSCAPE_DUMP_RECORDS=<path>` on a report run to capture the
records document that crosses that boundary (debugging, fixture refresh).

## Options

All optional; every flag is prefixed `--report-fairscape-`.

| Flag | Default | Effect |
| ---- | ------- | ------ |
| `--report-fairscape-path` | `ro-crate-metadata.json` | where to write the crate |
| `--report-fairscape-naan` | `59853` | ARK Name Assigning Authority Number |
| `--report-fairscape-name` | derived from the Snakefile | crate name |
| `--report-fairscape-description` | derived from the Snakefile | crate description (min 10 chars) |
| `--report-fairscape-author` | current user | author on the crate and its entities |
| `--report-fairscape-keywords` | `snakemake,workflow` | comma-separated |
| `--report-fairscape-license` | CC-BY-4.0 | license URL on the crate root |
| `--report-fairscape-version` | `1.0` | version on the crate root |
| `--report-fairscape-expand-directories` | off | register one Dataset per file inside each `directory()` output |
| `--report-fairscape-expand-max-files` | `1000` | cap per expanded directory (sorted walk, so the cap is deterministic) |
| `--report-fairscape-schemas` | off | infer an EVI Schema per data file (reads the data) |
| `--report-fairscape-no-link-inverses` | on | skip completing the crate against EVI's `owl:inverseOf` pairs |
| `--report-fairscape-no-evidence-graph` | on | skip `ro-crate-prov-graph.json/.html` |
| `--report-fairscape-no-linkml` | on | skip `ro-crate-linkml.yaml` |
| `--report-fairscape-no-datasheet` | on | skip `ro-crate-datasheet.html` + `ai_ready_score.json` |
| `--report-fairscape-preview` | off | also write `ro-crate-preview.html` |
| `--report-fairscape-croissant` | off | also write a Croissant JSON-LD export |
| `--report-fairscape-merkle` | off | also write a SHA-256 Merkle tree (reads every file) |

The on-by-default artifacts read only the crate JSON; everything that touches
data files is opt-in.

## Derived artifacts

After writing the crate, the reporter runs fairscape-cli's single-crate build
pipeline in the CLI's own order (link inverses → `EVI:inputs`/`EVI:outputs` →
evidence graph → LinkML → datasheet).

| File | What |
| ---- | ---- |
| `ro-crate-metadata.json` (rewritten) | completed against EVI's `owl:inverseOf` pairs; root gains `EVI:inputs`/`EVI:outputs` and `localEvidenceGraph` |
| `ro-crate-prov-graph.json` / `.html` | evidence graph rooted at the first EVI output, plus interactive visualization |
| `ro-crate-linkml.yaml` | the D4D/LinkML translation of the crate root |
| `ro-crate-datasheet.html` + `ai_ready_score.json` | human-readable datasheet and the AI-Ready score |
| EVI `Schema` node per data file | inferred columns/types, linked from the Dataset via `evi:Schema`; extensions csv/tsv/parquet/h5/hdf5/hea/dcm (`--report-fairscape-schemas`) |

Schema ARKs are minted deterministically (hashed from the Dataset's ARK,
overriding the CLI's random uuid via `infer_schema(guid=...)`), so the
ARK-stability guarantee below survives `--report-fairscape-schemas`.

## What ends up in the crate

Mirrors [nf-fairscape](https://github.com/fairscape/nf-fairscape)'s emission:

| Node | Snakemake source |
| ---- | ---------------- |
| Run Computation | the whole run; `usedDataset` = root inputs no job produced, `generated` = terminal outputs no job consumed, start/end = min/max job times |
| Job Computation (one per executed job) | `command` = the resolved shell command and `parameter`/inputs from the persistence `MetadataRecord`; outputs from the report `JobRecord`; wildcards in the name |
| Workflow Software | the Snakefile |
| Snakemake Software | the engine, versioned |
| Rule Software (one per rule) | `description` = the rule's action source as written (for `script:` rules that is the full script source — Snakemake loads it for the report); `contentUrl` = the defining file (see below); `containerImage`/`condaEnvironment` when declared |
| Dataset (one per unique file) | inputs, outputs, and configfiles (configfiles get `isPartOf` → workflow Software, keeping them out of run inputs) |

Both edge directions are written (`generated` and `generatedBy`).

ARKs are `ark:{naan}/{prefix}-{slug}-{sha1(source)[:7]}` and hash only
run-independent strings (Snakefile path, rule name, rule + sorted outputs, file
path) — so re-running the report, and even fully re-executing the workflow
(`--forceall`), reproduces identical identifiers. `tools/run-examples.sh`
asserts this.

Files under the crate directory get a crate-relative `contentUrl`; files
outside it — or already deleted, like `temp()` intermediates — get `localPath`
("was here when this ran").

### What a rule's Software `contentUrl` points at

| Rule action | `contentUrl` | `format` | works? |
| ----------- | ------------ | -------- | ------ |
| `script: "scripts/x.py"` | the script file, crate-relative when it is under the crate directory, else its absolute path | the script's language (`python`, `r`, …) | yes — proven by `examples/python-script` |
| `notebook:` | same resolution as `script:` | notebook language | expected (same code path); not yet covered by an example |
| `wrapper:` | the wrapper's resolved URL (e.g. the snakemake-wrappers raw URL) | wrapper language | expected; not yet covered by an example |
| `shell:` / `run:` | the Snakefile | `snakemake` | yes |
| script/notebook/wrapper path containing a wildcard | falls back to the Snakefile (there is no single defining file) | `snakemake` | yes (by construction) |

`script:`/`notebook:`/`wrapper:` jobs record no shell command in the
persistence metadata, so their Computation's `command` falls back to
`script: scripts/x.py` (etc.) instead of being empty.

A script invoked through `shell: "python scripts/foo.py"` is **not** found —
Snakemake treats the path as an opaque token in the shell string. It appears in
the crate only if also listed under `input:`, and then as a Dataset, not
Software.

## Which files the crate sees

**Every declared output of every executed job — nothing needs to be flagged.**
The report interface carries two separate channels: `results` holds only files
marked `report(...)` in the workflow (that's what the HTML reporter showcases),
while `jobs` covers the whole DAG — every job record lists every file in its
rule's `output:`, and its `input:` list comes from the persistence metadata.
This plugin reads `jobs` and ignores `results`, so intermediates are captured
automatically; none of the example workflows use `report()` at all.

| File | In the crate? |
| ---- | ------------- |
| any file in a rule's `output:` | yes — Dataset with `generatedBy`, wildcards resolved |
| intermediates consumed downstream | yes — same as any output |
| `temp()` intermediates (deleted after use) | yes, with full provenance edges; no `contentSize` and `localPath` instead of `contentUrl`, since the bytes are gone |
| `directory()` outputs | yes — one Dataset for the directory; with `--report-fairscape-expand-directories`, also one Dataset per file inside (`isPartOf` → the directory, `generatedBy` → its producer, capped, sorted walk, `.snakemake_timestamp` skipped) and the directory gains its recursive `contentSize`. Expanded files are deliberately not added to the Computation's `generated` — the directory stands for them |
| root inputs no job produced | yes — Dataset without `generatedBy`, listed in the run's `usedDataset` |
| configfiles | yes — `isPartOf` → workflow Software |
| files a rule writes **without declaring them in `output:`** | no — Snakemake itself has no record of them (and undeclared outputs break its own rerun/caching logic, so they're a workflow bug anyway) |
| `log:` files | not yet — the persistence metadata does record them (`MetadataRecord.log`), so this is addable |
| `benchmark:` files | no — not part of job outputs or metadata |

**Final outputs are derived, not declared:** the run Computation's `generated`
is the set of outputs no other job consumed. That reproduces "what the user
asked for" in the normal case (the target rule `all` has no outputs, so it
produces no job record — its inputs are exactly the terminal outputs). Caveat:
a requested file that is *also* consumed by another job counts as an
intermediate here and drops out of the run's `generated` (its Dataset and edges
remain).

## Why post-hoc?

Snakemake offers three places to hook provenance capture; this plugin uses the
first, which is also what the official WRROC plugin
([snakemake/snakemake-report-plugin-rocrate](https://github.com/snakemake/snakemake-report-plugin-rocrate),
early-stage, unreleased) chose.

**1. Report plugin, separate invocation (this plugin).** Snakemake persists
per-job metadata (resolved shell command, inputs, params, conda env, container,
times) into `.snakemake/metadata` during every run; `--reporter fairscape`
re-reads it afterwards.
*Pros:* zero runtime risk and zero overhead (a crash in the reporter can never
fail or slow a run); works on runs that finished before the plugin was
installed; re-runnable with different options; the sanctioned extension point
built exactly for this.
*Cons:* a second command to remember; sees only what persistence kept — no
original CLI line, no failed jobs (a failed job writes no metadata beyond an
`incomplete` flag), `temp()` files may already be deleted (their Datasets lose
`contentSize`), and a later run of the same workflow overwrites the metadata
(last run wins). The Snakefile must still parse at report time.

**2. Report plugin, same invocation (`--report-after-run`).** Snakemake can run
the reporter automatically at the end of the run — but as of snakemake 9.25.1
the CLI wiring blocks custom reporters: `--report-after-run` requires
`--report`, and `--report` force-selects the html reporter
(`snakemake/cli.py:2071-2078`). If that upstream wiring is relaxed, this plugin
would work there unchanged — same data, just triggered automatically.

**3. Logger plugin (live, during execution).** The only genuinely
during-execution extension point (`snakemake-interface-logger-plugins`)
receives log events as jobs start and finish — the only place that could see
failed jobs or the true command line.
*Cons:* it gets log records, not the DAG/persistence data contract, so the
whole crate assembly would have to be reconstructed from event payloads; it
runs in-process where an error can disturb the run; and it's a logging API, not
a provenance one. Nextflow needs the observer approach because it keeps no
queryable per-task metadata after the run — Snakemake does, which is exactly
what makes post-hoc viable and simpler here.

## Undeclared interfaces this relies on

The declared report-plugin contract (`ReporterBase`,
snakemake-interface-report-plugins 1.3.0) exposes rules/jobs/configfiles/dag,
but three load-bearing pieces are outside it (each wrapped so absence degrades
the crate rather than failing the report):

- `dag.workflow.persistence.metadata(f)` → `MetadataRecord` (record format
  version 6, `snakemake/persistence/__init__.py`) — the only source of the
  resolved `shellcmd`, `input` list, and `params` per job.
- `dag.workflow.main_snakefile` — the workflow identity that ARKs hash.
- `job_record.job.wildcards_dict` — only `.rule` is declared on the live job.

Developed and tested against snakemake 9.25.1 /
snakemake-interface-report-plugins 1.3.0.

## Known limits

- The run Computation's `command` is literally `snakemake` — the original
  command line is not recorded in the metadata the report step can see (see
  "Why post-hoc?").
- Jobs that failed or were never run leave no persistence metadata and are
  absent from the crate (only successful work is described).
- A rule with no outputs (like a bare `all` target) produces no job record and
  no Computation.
- No per-file checksums yet; `md5` fields are absent from Datasets, which costs
  the AI-Ready *verifiable* criterion.

## Development

```bash
pip install '.[artifacts,validate]'    # NOT -e: see below
pip install snakemake
tools/run-examples.sh
```

**Install non-editable.** Snakemake's plugin registry discovers plugins with
`pkgutil.iter_modules`, which does not see setuptools editable installs — a
`pip install -e .` plugin is silently absent from `--reporter`. Re-run
`pip install .` after each change.

`tools/run-examples.sh` runs all four examples (`letters-chain` — 3-rule linear
chain; `sample-fanout` — wildcard fan-out over 3 samples + aggregation +
configfile + root inputs + `--report-fairscape-schemas`; `python-script` — a
`script:` rule, proving the Software `contentUrl` points at the .py file;
`dir-plots` — a `directory()` output with
`--report-fairscape-expand-directories`), asserts every derived artifact
exists, validates each crate with
`fairscape_models.ROCrateV1_2.model_validate` plus a dangling-ARK check
(`tools/validate_crate.py`), and asserts ARK stability across a second report
invocation. CI runs exactly this.

Releasing a new version: see [RELEASING.md](RELEASING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
