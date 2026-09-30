# Changelog

## 0.2.0

- No longer uses `fairscape-cli`, which is being retired. The inverse links,
  `EVI:inputs`/`EVI:outputs`, evidence graph and datasheet come from
  `fairscape-artifacts` (the `[artifacts]` extra now names it, `>=0.2.0`);
  the LinkML/D4D and Croissant exports are `fairscape-conversion`'s own
  plugins; schema inference goes through `fairscape_conversion.core.schemas`
  over `fairscape_models.schema` (new `[schemas]` extra for the readers).
- File names follow `fairscape-artifacts`: `ro-crate-evidence-graph.json/.html`
  replace `ro-crate-prov-graph.*`; the AI-Ready score is
  `ai-ready-presentation.json` + `ai-ready-review.html`, written only when the
  grader is installed (`fairscape-artifacts[review]`). The Croissant export is
  `ro-crate-croissant.json` as before.
- `--report-fairscape-merkle` is accepted but ignored: the Merkle tree was a
  fairscape-cli feature.
- When a step is skipped the note says what to run to get it.
- Requires `fairscape-conversion >=0.2.2,<0.3`.

## 0.1.0

First release.

- `snakemake --reporter fairscape` writes a FAIRSCAPE EVI RO-Crate for a
  completed run: a run Computation, one Computation per executed job, Software
  entities for the Snakefile, the engine and each rule, and a Dataset per file.
- Derived artifacts generated through `fairscape-cli`: inverse linking,
  `EVI:inputs`/`EVI:outputs`, evidence graph (`ro-crate-prov-graph.json/.html`),
  LinkML/D4D export, datasheet and AI-Ready score. Opt-in: schema inference,
  `directory()` expansion, preview, Croissant, Merkle tree.
- Deterministic ARKs: identifiers hash only run-independent strings, so
  re-reporting or re-executing a workflow reproduces them exactly.
- The Snakefile-to-EVI mapping lives in `fairscape-conversion`
  (`plugins/snakemake`); this package only extracts plain data from Snakemake.
- The derived artifacts require fairscape-cli 1.2.10 or newer (pinned by the
  `artifacts` extra); without it the crate is written and the steps after it
  are skipped with a note.
