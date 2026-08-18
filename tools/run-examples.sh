#!/usr/bin/env bash
# Run every example workflow, generate its FAIRSCAPE crate, validate it, and
# assert ARK stability across a second report invocation.
set -euo pipefail

cd "$(dirname "$0")/.."
root=$(pwd)
snakemake=${SNAKEMAKE:-snakemake}

arks() { python3 -c "import json,sys; [print(n['@id']) for n in json.load(open(sys.argv[1]))['@graph']]" "$1"; }

for example in examples/*/; do
    name=$(basename "$example")
    echo "=== $name"
    (
        cd "$example"
        flags=""
        [ -f reporter-flags ] && flags=$(cat reporter-flags)
        $snakemake --cores 2 --quiet all >/dev/null
        $snakemake --reporter fairscape $flags >/dev/null 2>&1
        python3 "$root/tools/validate_crate.py" ro-crate-metadata.json
        for artifact in ro-crate-datasheet.html ai_ready_score.json \
                        ro-crate-linkml.yaml ro-crate-prov-graph.json \
                        ro-crate-prov-graph.html; do
            if [ ! -f "$artifact" ]; then
                echo "  MISSING derived artifact: $artifact" >&2
                exit 1
            fi
        done
        echo "  derived artifacts present (datasheet, ai-ready, linkml, prov-graph)"
        arks ro-crate-metadata.json > /tmp/arks-before.$$
        $snakemake --reporter fairscape $flags >/dev/null 2>&1
        arks ro-crate-metadata.json > /tmp/arks-after.$$
        if diff -q /tmp/arks-before.$$ /tmp/arks-after.$$ >/dev/null; then
            echo "  ARKs stable across report re-run"
        else
            echo "  ARKs CHANGED across report re-run" >&2
            diff /tmp/arks-before.$$ /tmp/arks-after.$$ >&2 || true
            exit 1
        fi
        rm -f /tmp/arks-before.$$ /tmp/arks-after.$$
    )
done
echo "ALL EXAMPLES PASS"
