# Changelog

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
- The derived artifacts require fairscape-cli 1.2.10 or newer; against an older
  one the crate is written and the steps after it are skipped with a note.
